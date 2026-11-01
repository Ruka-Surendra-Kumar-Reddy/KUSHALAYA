"""Care checks that run on the job timer (every few minutes).

* Missed visits: a visit still not started 3 hours after its time becomes
  "missed"; the care manager is emailed and the family is told it will be rebooked.
* Wearable bands: offline / low battery alerts (see band_checks.py).
* Reassessments due: once a day (after 08:00 India time) each agency's
  managers get one email listing clients whose 6-monthly assessment is due.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.care_job import CareJob
from app.models.elder import Elder
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

MISSED_AFTER = timedelta(hours=3)
IST = timezone(timedelta(hours=5, minutes=30))
DIGEST_HOUR_IST = 8


def _ist_date(iso: str) -> str:
    """due_at is stored as a UTC ISO string; show the IST calendar date."""
    try:
        dt = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return str(iso)[:10]
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST).date().isoformat()
DIGEST_KEY = "reassessment_digest_sent"
_INACTIVE = ("inactive", "archived", "deleted", "discharged")


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def mark_missed_visits(db: Session, *, now: datetime | None = None) -> list[int]:
    from app.livewell.care_jobs import _missed_notices

    now = now or datetime.now(timezone.utc)
    cutoff = now - MISSED_AFTER
    rows = (
        db.query(CareJob)
        .filter(
            CareJob.status.in_(("scheduled", "on_the_way")),
            CareJob.scheduled_at.isnot(None),
            CareJob.scheduled_at <= cutoff,
            CareJob.checked_in_at.is_(None),
            # An assessment with answers saved (or started from the office) is in
            # progress, not missed: the checklist can still be finished.
            or_(CareJob.kind != "assessment", CareJob.assessment_id.is_(None)),
        )
        .all()
    )
    if not rows:
        return []
    from app.livewell.live_location import clear as clear_live

    for job in rows:
        job.status = "missed"
        clear_live(db, job.id)  # no live location after the visit window
    # Commit first: if it fails nobody is told, and the next run retries cleanly.
    db.commit()
    for job in rows:
        elder = db.get(Elder, job.elder_id)
        if elder:
            _missed_notices(db, elder, job)
    db.commit()
    return [j.id for j in rows]


def send_reassessment_digests(db: Session, *, now: datetime | None = None) -> list[int]:
    """One email per agency per day listing clients whose reassessment is due."""
    from app.livewell.email_notifications import get_rules, send, staff_recipients
    from app.livewell.reassessment import due_list

    now = now or datetime.now(timezone.utc)
    local = now.astimezone(IST)
    if local.hour < DIGEST_HOUR_IST:
        return []
    today = local.date().isoformat()
    sent: list[int] = []
    for tenant in db.query(Tenant).all():
        cfg = dict(tenant.workflow_config or {})
        if cfg.get(DIGEST_KEY) == today:
            continue
        elders = (
            db.query(Elder)
            .filter(Elder.tenant_id == tenant.id)
            .all()
        )
        elders = [e for e in elders if (e.status or "").lower() not in _INACTIVE]
        due = due_list(db, elders, now=now)
        cfg[DIGEST_KEY] = today
        tenant.workflow_config = cfg
        flag_modified(tenant, "workflow_config")
        db.commit()
        if not due:
            continue
        rule = get_rules(tenant)["staff"]["reassessment"]
        if not rule["enabled"]:
            continue
        # Each client's own manager, the admins and extra addresses — one email per person.
        by_person: dict[str, list[str]] = {}
        for r in due:
            elder = db.get(Elder, r["elder_id"])
            line = f"• {r['elder_name']} — {r['label']}" + (
                " (overdue)" if r["overdue"] else f" (due {_ist_date(r['due_at'])})" if r["due_at"] else ""
            )
            for to in staff_recipients(db, elder, "reassessment"):
                by_person.setdefault(to, []).append(line)
        for to, lines in by_person.items():
            send(
                [to],
                f"{len(lines)} assessment{'s' if len(lines) != 1 else ''} to book",
                "These clients need their home safety assessment booked:\n"
                + "\n".join(lines)
                + "\nBook them from Schedule → Waiting to be scheduled.",
                family=False,
            )
        sent.append(tenant.id)
    return sent


def run(db: Session) -> dict:
    missed = mark_missed_visits(db)
    digests = send_reassessment_digests(db)
    try:
        from app.livewell.band_checks import check_bands

        bands = check_bands(db)
    except Exception:  # a band check problem must not stop the other checks
        db.rollback()
        logger.exception("band_checks_failed")
        bands = []
    try:
        from app.livewell.kushlife_weekly import draft_weekly_summaries

        weekly = draft_weekly_summaries(db)  # Monday 07:00 IST onwards; one per client per week
    except Exception:
        db.rollback()
        logger.exception("kushlife_weekly_failed")
        weekly = []
    try:
        from app.livewell.kushlife_monthly import draft_monthly_letters

        monthly = draft_monthly_letters(db)  # 1st of the month 07:00 IST onwards; one per client per month
    except Exception:
        db.rollback()
        logger.exception("kushlife_monthly_failed")
        monthly = []
    try:
        from app.livewell.care_series import top_up_series

        series = top_up_series(db)  # repeating visits: keep ~4 weeks of jobs ahead (idempotent)
    except Exception:
        db.rollback()
        logger.exception("care_series_top_up_failed")
        series = {}
    return {
        "missed_jobs": missed,
        "reassessment_digests": digests,
        "band_alerts": bands,
        "kushlife_weekly": weekly,
        "kushlife_monthly": monthly,
        "series_jobs": series,
    }
