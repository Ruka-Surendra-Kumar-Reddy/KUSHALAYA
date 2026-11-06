"""Business alerts to the team by email and WhatsApp: new leads, assessments, vendors, stuck leads.

Who gets each one comes from Settings → Notifications (``email_notifications`` rules). The
extra addresses there also get WhatsApp when they belong to a staff login with a mobile number.
Alerts never raise: a failed message must not undo the lead or vendor that was just saved.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.pipeline_constants import ACTIVITY_STAGE_CHANGE
from app.livewell import email_notifications as en
from app.models.elder_prospect import ElderProspect
from app.models.pipeline_activity import PipelineActivity
from app.models.tenant import Tenant
from app.models.user import User

logger = logging.getLogger(__name__)

#: Stuck-lead messages go out in the working day only.
ALERT_HOURS_IST = range(9, 20)
MAX_LEADS_LISTED = 20


def _phones(db: Session, tenant_id: int, rule: dict) -> list[str]:
    from app.services.notifications.types import normalize_phone

    roles = (["TENANT_ADMIN"] if rule["admins"] else []) + (["CARE_MANAGER"] if rule["manager"] else [])
    extra = {e.lower() for e in rule["extra"]}
    rows = db.query(User).filter(User.tenant_id == tenant_id, User.status == "ACTIVE").all()
    found = [normalize_phone(u.phone) for u in rows if u.role in roles or (u.email or "").lower() in extra]
    return sorted({p for p in found if p})


def _send_whatsapp(phones: list[str], text: str) -> None:
    from app.services.notifications.factory import get_whatsapp_provider

    for to in phones:
        try:
            get_whatsapp_provider().send_team_text(to, text)
        except Exception:  # noqa: BLE001
            logger.exception("team_alert_whatsapp_failed")


def alert_team(
    db: Session,
    tenant_id: int,
    event: str,
    title: str,
    body: str,
    *,
    path: str = "",
    email: str = "all",
    background: bool = True,
) -> None:
    """``email``: "all" follows the rule, "extra" only the added people (the event already
    emails the rest), "none" WhatsApp only."""
    try:
        rule = en.get_rules(db.get(Tenant, tenant_id))["staff"].get(event)
        if not rule or not rule["enabled"]:
            return
        to = {"all": en.agency_recipients(db, tenant_id, event), "extra": rule["extra"], "none": []}[email]
        if to:
            with en.email_context(path):
                en.send(to, title, body, family=False, background=background)
        if rule["whatsapp"]:
            phones = _phones(db, tenant_id, rule)
            line = " ".join(f"{title}. {body}".split())[:900] + (f" {en.OPS_URL}{path}" if path else "")
            if background:
                threading.Thread(target=_send_whatsapp, args=(phones, line), daemon=True).start()
            else:
                _send_whatsapp(phones, line)
    except Exception:  # noqa: BLE001
        logger.exception("team_alert_failed event=%s", event)


def _naive(t: datetime | None) -> datetime | None:
    return t.astimezone(timezone.utc).replace(tzinfo=None) if t is not None and t.tzinfo else t


def stuck_leads(db: Session, tenant_id: int, now: datetime) -> list[tuple[ElderProspect, str, int]]:
    """(lead, phase, whole days in it) for open leads due an alert. ``now`` is naive UTC."""
    from app.livewell.sales_pipeline import STAGE_LABELS, board_stage

    settings = en.get_rules(db.get(Tenant, tenant_id))["lead_stuck"]
    moved = dict(
        db.query(PipelineActivity.elder_prospect_id, func.max(PipelineActivity.created_at))
        .filter(PipelineActivity.tenant_id == tenant_id, PipelineActivity.activity_type == ACTIVITY_STAGE_CHANGE)
        .group_by(PipelineActivity.elder_prospect_id)
        .all()
    )
    due = []
    for lead in db.query(ElderProspect).filter(ElderProspect.tenant_id == tenant_id).all():
        phase = board_stage(lead)
        limit = settings["days"].get(phase)
        entered = _naive(moved.get(lead.id) or lead.created_at)
        if not limit or entered is None:
            continue
        days = (now - entered).days
        if days < limit:
            continue
        alerted = _naive(lead.stage_alerted_at)
        if alerted is None or alerted < entered or now - alerted >= timedelta(days=settings["repeat_days"]):
            due.append((lead, STAGE_LABELS.get(phase, phase), days))
    return due


def run_stuck_lead_alerts(db: Session, now: datetime | None = None) -> int:
    """One combined message per tenant, so old leads cannot flood anyone's phone."""
    now = now or datetime.now(timezone.utc)
    if now.astimezone(ZoneInfo("Asia/Kolkata")).hour not in ALERT_HOURS_IST:
        return 0
    utc = _naive(now)
    sent = 0
    for (tenant_id,) in db.query(ElderProspect.tenant_id).distinct().all():
        due = stuck_leads(db, tenant_id, utc)
        if not due:
            continue
        due.sort(key=lambda d: -d[2])
        names = [
            f"{' '.join(filter(None, [lead.first_name, lead.last_name]))} ({phase}, {days} days)"
            for lead, phase, days in due[:MAX_LEADS_LISTED]
        ]
        more = len(due) - len(names)
        body = "; ".join(names) + (f"; and {more} more" if more > 0 else "")
        alert_team(
            db, tenant_id, "lead_stuck", f"{len(due)} lead{'s' if len(due) != 1 else ''} need attention",
            body, path="/kushalaya/enquiries", background=False,
        )
        for lead, _phase, _days in due:
            lead.stage_alerted_at = utc
        db.commit()
        sent += len(due)
    return sent
