"""Staff-raised emergency (Phase 3D, items 112–114).

The field team hears about an emergency by phone (from a caregiver or the
elder). A care manager / admin (ops) or a caregiver (field app) raises it; it
becomes a ``care_incidents`` row with ``kind="staff_emergency"``, severity
critical, so it shows wherever alerts show.

Until it is closed:

* an **owner** is assigned (default: the raiser; a caregiver's emergency goes to
  the client's care manager when there is one);
* a **checklist** of steps (call the elder, call the family, ambulance /
  hospital, partner notified, caregiver sent) — each tick is stored on
  ``incident.details["steps"]`` and written to the timeline as a ``step`` event;
* if nobody touches it for ``idle_minutes`` (default 10) it is escalated once
  per idle stretch by the existing escalation job (``run_idle_scan``);
* closing needs an outcome (resolved at home / hospital admission / false alarm
  / other) and a note.

The family sees a plain status only ("Emergency — our team is handling it",
then the outcome), through the family-hub mirror.

Emergency partners (ambulance / hospital / internal) live on
``tenant.workflow_config["emergency"]["partners"]``. "Notify partner" emails a
signed link (``secrets.token_urlsafe``; only its SHA-256 is stored) scoped to
one incident and valid for 48 h. The partner's "Received" / "On the way" /
"Done" replies are ``partner`` events on the timeline.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.rbac import CARE_MANAGER, CAREGIVER, SYSTEM_ADMIN, TENANT_ADMIN
from app.core.responses import raise_bad_request, raise_not_found
from app.livewell import incident_service as inc
from app.models.elder import Elder
from app.models.incident import OPEN_STATUSES, Incident, IncidentEvent, IncidentPartnerLink
from app.models.tenant import Tenant
from app.models.user import User

KIND = "staff_emergency"
CONFIG_KEY = "emergency"
DEFAULT_IDLE_MINUTES = 10
LINK_HOURS = 48

EMERGENCY_TYPES: dict[str, str] = {
    "fall": "Fall",
    "chest_breathing": "Chest pain / breathing",
    "unresponsive": "Unresponsive",
    "injury": "Injury",
    "other": "Other",
}
REPORTERS: dict[str, str] = {
    "caregiver": "Caregiver",
    "elder": "The client",
    "family": "Family",
    "other": "Someone else",
}
STEPS: dict[str, str] = {
    "call_elder": "Called the client",
    "call_family": "Called the family",
    "ambulance": "Ambulance / hospital arranged",
    "partner_notified": "Partner notified",
    "caregiver_sent": "Caregiver sent",
}
EMERGENCY_OUTCOMES: dict[str, str] = {
    "resolved_home": "Resolved at home",
    "hospital_admission": "Admitted to hospital",
    "false_alarm": "False alarm",
    "other": "Other",
}
PARTNER_TYPES = ("ambulance", "hospital", "internal")
PARTNER_STATUSES: dict[str, str] = {
    "received": "Received",
    "on_the_way": "On the way",
    "done": "Done",
}

FAMILY_OPEN_TEXT = "Emergency — our team is handling it"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _name(user: User | None) -> str:
    if not user:
        return ""
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or (user.email or "")


def _clip(value: Any, n: int) -> str:
    return str(value or "").strip()[:n]


# ---------------------------------------------------------------------------
# Settings: emergency partners + idle minutes (tenant.workflow_config)
# ---------------------------------------------------------------------------


def get_config(tenant: Tenant | None) -> dict:
    raw = ((tenant.workflow_config or {}) if tenant else {}).get(CONFIG_KEY) or {}
    partners = []
    for p in raw.get("partners") or []:
        if isinstance(p, dict) and p.get("id") and p.get("name"):
            partners.append(
                {
                    "id": str(p["id"]),
                    "name": _clip(p.get("name"), 200),
                    "phone": _clip(p.get("phone"), 40),
                    "email": _clip(p.get("email"), 255),
                    "type": p.get("type") if p.get("type") in PARTNER_TYPES else "internal",
                }
            )
    try:
        idle = int(raw.get("idle_minutes") or DEFAULT_IDLE_MINUTES)
    except (TypeError, ValueError):
        idle = DEFAULT_IDLE_MINUTES
    return {"partners": partners, "idle_minutes": max(2, min(240, idle))}


def save_config(db: Session, tenant: Tenant, body: dict) -> dict:
    current = get_config(tenant)
    if "partners" in body:
        partners = []
        for p in (body.get("partners") or [])[:30]:
            if not isinstance(p, dict):
                continue
            name = _clip(p.get("name"), 200)
            if not name:
                continue
            email = _clip(p.get("email"), 255)
            if email and not _EMAIL.match(email):
                raise_bad_request(f"Check the email for {name}")
            partners.append(
                {
                    "id": _clip(p.get("id"), 40) or uuid.uuid4().hex[:12],
                    "name": name,
                    "phone": _clip(p.get("phone"), 40),
                    "email": email,
                    "type": p.get("type") if p.get("type") in PARTNER_TYPES else "internal",
                }
            )
        current["partners"] = partners
    if body.get("idle_minutes") not in (None, ""):
        current["idle_minutes"] = max(2, min(240, int(body["idle_minutes"])))
    cfg = dict(tenant.workflow_config or {})
    cfg[CONFIG_KEY] = current
    tenant.workflow_config = cfg
    flag_modified(tenant, "workflow_config")
    db.commit()
    return get_config(tenant)


def options(db: Session, tenant_id: int | None) -> dict:
    tenant = db.get(Tenant, tenant_id) if tenant_id else None
    cfg = get_config(tenant)
    as_list = lambda d: [{"value": k, "label": v} for k, v in d.items()]  # noqa: E731
    return {
        "types": as_list(EMERGENCY_TYPES),
        "reporters": as_list(REPORTERS),
        "steps": as_list(STEPS),
        "outcomes": as_list(EMERGENCY_OUTCOMES),
        "partner_statuses": as_list(PARTNER_STATUSES),
        "partners": cfg["partners"],
        "idle_minutes": cfg["idle_minutes"],
    }


# ---------------------------------------------------------------------------
# Scoping helpers
# ---------------------------------------------------------------------------


def caregiver_elder_ids(db: Session, caregiver_id: int, *, now: datetime | None = None) -> set[int]:
    """Clients a caregiver works with now: active assignments plus non-cancelled
    visits from yesterday to tomorrow (IST days). Old visits don't count."""
    from app.livewell.care_jobs import IST
    from app.models.assignment import Assignment
    from app.models.care_job import CareJob

    at = now or _now()
    day_start = at.astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    # DB stores UTC; pass UTC bounds so SQLite (naive strings) and Postgres agree.
    lo = (day_start - timedelta(days=1)).astimezone(timezone.utc)
    hi = (day_start + timedelta(days=2)).astimezone(timezone.utc)
    ids = {
        r[0]
        for r in db.query(CareJob.elder_id)
        .filter(
            CareJob.caregiver_id == caregiver_id,
            CareJob.status != "cancelled",
            CareJob.scheduled_at >= lo,
            CareJob.scheduled_at < hi,
        )
        .all()
    }
    ids |= {
        r[0]
        for r in db.query(Assignment.elder_id)
        .filter(Assignment.caregiver_id == caregiver_id, Assignment.status == "ACTIVE")
        .all()
    }
    return ids


def _emergency(db: Session, incident_id: int, tenant_id: int | None) -> Incident:
    row = inc.get_incident(db, incident_id, tenant_id=tenant_id)
    if row.kind != KIND:
        raise_bad_request("Not an emergency")
    return row


def _require_open(row: Incident) -> None:
    if row.status not in OPEN_STATUSES:
        raise_bad_request("This emergency is already closed")


def _details(row: Incident) -> dict:
    return dict(row.details) if isinstance(row.details, dict) else {}


def _save_details(row: Incident, details: dict) -> None:
    row.details = details
    flag_modified(row, "details")


# ---------------------------------------------------------------------------
# Raise
# ---------------------------------------------------------------------------


def raise_emergency(
    db: Session,
    user: User,
    *,
    elder: Elder,
    emergency_type: str,
    reported_by: str,
    reporter_phone: str | None = None,
    note: str | None = None,
    job_id: int | None = None,
    now: datetime | None = None,
) -> tuple[Incident, bool]:
    """Open (or join) the client's emergency. Returns ``(incident, created)``."""
    etype = (emergency_type or "").strip().lower()
    if etype not in EMERGENCY_TYPES:
        raise_bad_request(f"type must be one of {', '.join(EMERGENCY_TYPES)}")
    reporter = (reported_by or "").strip().lower()
    if reporter not in REPORTERS:
        raise_bad_request(f"reported_by must be one of {', '.join(REPORTERS)}")
    text = _clip(note, 2000)
    if etype == "other" and not text:
        raise_bad_request("Say what happened")
    at = now or _now()
    who = _name(user)
    summary = f"{EMERGENCY_TYPES[etype]} — reported by {REPORTERS[reporter].lower()}" + (
        f" ({_clip(reporter_phone, 40)})" if (reporter_phone or "").strip() else ""
    )

    # Two calls about the same emergency must not open two: join the open one.
    # Lock the client row first so two raises at once serialise and the second joins.
    from app.livewell.family_service_requests import lock_elder

    elder = lock_elder(db, elder)
    existing = (
        db.query(Incident)
        .filter(Incident.elder_id == elder.id, Incident.kind == KIND, Incident.status.in_(list(OPEN_STATUSES)))
        .order_by(Incident.id.desc())
        .first()
    )
    if existing:
        inc.record_event(
            db, existing, "note", channel="portal", actor_user_id=user.id,
            detail=f"Raised again by {who}: {summary}" + (f" — {text}" if text else ""), at=at, commit=True,
        )
        return existing, False

    legacy_id = f"semg_{uuid.uuid4().hex[:12]}"
    row, _created = inc.open_incident(
        db,
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
        kind=KIND,
        severity="critical",
        source="staff",
        note=f"{summary}" + (f". {text}" if text else ""),
        legacy_id=legacy_id,
        now=at,
    )
    owner_id = user.id
    if user.role == CAREGIVER and elder.manager_user_id:
        owner_id = elder.manager_user_id
    row.owner_user_id = owner_id
    # The raiser is already on it: the "nobody acknowledged" ladder does not apply.
    row.acknowledged_at = at
    row.acknowledged_by_user_id = user.id
    row.status = "acknowledged"
    _save_details(
        row,
        {
            "type": etype,
            "type_label": EMERGENCY_TYPES[etype],
            "reported_by": reporter,
            "reported_by_label": REPORTERS[reporter],
            "reporter_phone": _clip(reporter_phone, 40) or None,
            "raised_by_user_id": user.id,
            "raised_by_name": who,
            "raised_by_role": user.role,
            "job_id": job_id,
            "steps": {},
        },
    )
    inc.record_event(
        db, row, "raised", channel="portal", actor_user_id=user.id,
        detail=f"Emergency raised by {who}: {summary}" + (f" — {text}" if text else ""), at=at,
    )
    owner = db.get(User, owner_id)
    inc.record_event(
        db, row, "assigned", channel="portal", actor_user_id=user.id,
        detail=f"Owner: {_name(owner) or 'unassigned'}", at=at,
    )
    db.commit()
    db.refresh(row)
    _alert_staff(db, elder, row, who, summary, text)
    from app.livewell import sos_siren

    # The family is told only when staff tap "Notify family" (owner, 29 Oct); a
    # manager or admin raising it has confirmed it is real, a caregiver has not.
    sos_siren.start(
        db, row, source="caregiver" if user.role == CAREGIVER else "ops", presser=user, now=at,
        confirmed_by=user if user.role in sos_siren.STAFF_ACK_ROLES else None,
    )
    return row, True


def _mirror_open_to_family(db: Session, elder: Elder, row: Incident, *, note: str = "") -> None:
    """Plain family status: no reporter, phone, partner or clinical detail.
    Sent by sos_siren.notify_family once staff choose to tell the family."""
    from app.livewell.family_care_hub import FamilyCareHubService, _hub, _iso, _save_hub

    hub = _hub(elder)
    hub["incidents"] = [
        {
            "id": row.legacy_id,
            "kind": "emergency",
            "note": FAMILY_OPEN_TEXT,
            "status": "open",
            "created_at": _iso(),
            "created_by": "care team",
            "incident_db_id": row.id,
        },
        *hub["incidents"],
    ][:50]
    _save_hub(db, elder, hub)
    FamilyCareHubService._push_alert(
        db, elder,
        title=FAMILY_OPEN_TEXT,
        body="We are with it now and will update you here." + note,
        severity="critical",
        incident_id=row.legacy_id,
    )
    try:
        from app.livewell.email_notifications import email_context, family_recipients, send

        with email_context("/alerts", (elder.first_name or "").strip()):
            send(family_recipients(db, elder, "sos"), FAMILY_OPEN_TEXT,
                 f"Our care team is handling an emergency for {elder.first_name}. We will update you here." + note,
                 family=True)
    except Exception:  # noqa: BLE001
        inc.logger.exception("emergency_family_email_failed incident=%s", row.id)


def _alert_staff(db: Session, elder: Elder, row: Incident, who: str, summary: str, text: str) -> None:
    from app.livewell.email_notifications import email_staff

    name = f"{elder.first_name} {elder.last_name}".strip()
    email_staff(
        db, elder, "alert",
        f"EMERGENCY — {name}",
        f"{who} raised an emergency for {name}: {summary}." + (f"\n{text}" if text else "")
        + "\nOpen Alerts in KushAlaya Ops and work through the checklist.",
        path=f"/kushalaya/alerts?open={row.id}",
    )


# ---------------------------------------------------------------------------
# Process: steps, owner, close
# ---------------------------------------------------------------------------


def tick_step(
    db: Session,
    row: Incident,
    user: User,
    step: str,
    *,
    hospital_name: str | None = None,
    note: str | None = None,
    now: datetime | None = None,
) -> Incident:
    _require_open(row)
    key = (step or "").strip().lower()
    if key not in STEPS:
        raise_bad_request(f"step must be one of {', '.join(STEPS)}")
    hospital = _clip(hospital_name, 200)
    if key == "ambulance" and not hospital:
        raise_bad_request("Hospital name required")
    at = now or _now()
    details = _details(row)
    steps = dict(details.get("steps") or {})
    steps[key] = {
        "at": at.isoformat(),
        "by_user_id": user.id,
        "by_name": _name(user),
        **({"hospital_name": hospital} if hospital else {}),
        **({"note": _clip(note, 500)} if (note or "").strip() else {}),
    }
    details["steps"] = steps
    if hospital:
        details["hospital_name"] = hospital
    _save_details(row, details)
    inc.record_event(
        db, row, "step", channel="portal", actor_user_id=user.id,
        detail=STEPS[key] + (f" — {hospital}" if hospital else "") + (f" — {_clip(note, 500)}" if (note or "").strip() else ""),
        at=at,
    )
    db.commit()
    db.refresh(row)
    return row


def assign_owner(db: Session, row: Incident, actor: User, owner_id: int | None, *, now: datetime | None = None) -> Incident:
    _require_open(row)
    owner = db.get(User, owner_id or actor.id)
    if not owner or owner.tenant_id != row.tenant_id or owner.role not in (TENANT_ADMIN, CARE_MANAGER, SYSTEM_ADMIN):
        raise_bad_request("Owner must be a care manager or admin in this agency")
    row.owner_user_id = owner.id
    inc.record_event(
        db, row, "assigned", channel="portal", actor_user_id=actor.id,
        detail=f"Owner: {_name(owner)}", at=now or _now(),
    )
    db.commit()
    db.refresh(row)
    return row


def close(db: Session, row: Incident, user: User, *, outcome: str, note: str | None) -> Incident:
    """Close with an outcome + note; the family sees the outcome in plain words."""
    _require_open(row)
    outcome_n = (outcome or "").strip().lower()
    inc.resolve(db, row, outcome=outcome_n, note=note, user=user, notify_family=False)
    # Partner links stop working the moment the emergency is closed.
    at = _now()
    for link_row in db.query(IncidentPartnerLink).filter(IncidentPartnerLink.incident_id == row.id).all():
        if _expired(link_row, at):
            continue
        link_row.expires_at = at
    db.commit()
    _mirror_close_to_family(db, row)
    return row


def family_outcome_text(row: Incident) -> str:
    label = EMERGENCY_OUTCOMES.get(row.outcome or "", "Closed")
    if row.outcome == "hospital_admission":
        hospital = _details(row).get("hospital_name")
        return f"Emergency closed — admitted to hospital" + (f" ({hospital})" if hospital else "")
    if row.outcome == "other":
        return "Emergency closed by the care team"
    return f"Emergency closed — {label.lower()}"


def _mirror_close_to_family(db: Session, row: Incident) -> None:
    from app.livewell.family_care_hub import _hub, _save_hub

    elder = db.get(Elder, row.elder_id)
    if not elder:
        return
    text = family_outcome_text(row)
    hub = _hub(elder)
    for item in hub["incidents"]:
        if isinstance(item, dict) and str(item.get("id")) == str(row.legacy_id):
            item["note"] = text
            item["status"] = "resolved"
    _save_hub(db, elder, hub)
    inc.tell_family(db, row, text, "Reply in Messages if you need anything.")


# ---------------------------------------------------------------------------
# Idle escalation (called from incident_service.run_escalation_scan)
# ---------------------------------------------------------------------------


def _last_touch(db: Session, row: Incident) -> datetime:
    """Latest staff action or partner reply; the raise itself counts."""
    events = (
        db.query(IncidentEvent)
        .filter(IncidentEvent.incident_id == row.id)
        .order_by(IncidentEvent.at.desc(), IncidentEvent.id.desc())
        .all()
    )
    for e in events:
        if e.actor_user_id is not None or e.event == "partner":
            return inc._aware(e.at)
    return inc._aware(row.opened_at)


def run_idle_scan(db: Session, *, now: datetime | None = None, tenant_id: int | None = None) -> list[dict]:
    """Escalate an open emergency nobody has touched for ``idle_minutes``.

    Once per idle stretch: an ``escalated`` event after the last touch means it
    was already escalated, so a scan every 2 minutes does not re-send.
    """
    at = now or _now()
    q = db.query(Incident).filter(Incident.kind == KIND, Incident.status.in_(list(OPEN_STATUSES)))
    if tenant_id is not None:
        q = q.filter(Incident.tenant_id == tenant_id)
    out: list[dict] = []
    idle_by_tenant: dict[int, int] = {}
    for row in q.all():
        if row.tenant_id not in idle_by_tenant:
            idle_by_tenant[row.tenant_id] = get_config(db.get(Tenant, row.tenant_id))["idle_minutes"]
        idle = idle_by_tenant[row.tenant_id]
        touched = _last_touch(db, row)
        if (at - touched) < timedelta(minutes=idle):
            continue
        already = (
            db.query(IncidentEvent.id)
            .filter(IncidentEvent.incident_id == row.id, IncidentEvent.event == "escalated", IncidentEvent.at >= touched)
            .first()
        )
        if already:
            continue
        level = min(inc.MAX_ESCALATION_LEVEL, int(row.escalation_level or 0) + 1)
        inc.escalate(
            db, row, level=level, now=at, mark_escalated=True,
            reason=f"emergency untouched for {inc._minutes_between(touched, at)} min",
        )
        out.append({"incident_id": row.id, "level": level, "idle_minutes": idle})
    return out


# ---------------------------------------------------------------------------
# Partner hand-off
# ---------------------------------------------------------------------------


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def partner_links_for(db: Session, incident_id: int) -> list[dict]:
    rows = (
        db.query(IncidentPartnerLink)
        .filter(IncidentPartnerLink.incident_id == incident_id)
        .order_by(IncidentPartnerLink.id.asc())
        .all()
    )
    return [
        {
            "id": r.id,
            "name": r.partner_name,
            "type": r.partner_type,
            "email": r.partner_email,
            "phone": r.partner_phone,
            "sent_at": inc._aware(r.created_at),
            "expires_at": inc._aware(r.expires_at),
            "last_status": r.last_status,
            "last_status_label": PARTNER_STATUSES.get(r.last_status or "", None),
            "last_response_at": inc._aware(r.last_response_at),
        }
        for r in rows
    ]


def notify_partner(
    db: Session,
    row: Incident,
    user: User,
    partner_id: str,
    *,
    message: str | None = None,
    base_url: str | None = None,
    now: datetime | None = None,
) -> tuple[Incident, str]:
    """Email the partner a link to respond. Returns ``(incident, link)``."""
    _require_open(row)
    tenant = db.get(Tenant, row.tenant_id)
    partner = next((p for p in get_config(tenant)["partners"] if p["id"] == str(partner_id)), None)
    if not partner:
        raise_not_found("Partner not found — add it in Settings → Emergency partners")
    at = now or _now()
    token = secrets.token_urlsafe(32)
    link_row = IncidentPartnerLink(
        incident_id=row.id,
        tenant_id=row.tenant_id,
        token_hash=_hash(token),
        partner_name=partner["name"],
        partner_type=partner["type"],
        partner_email=partner["email"] or None,
        partner_phone=partner["phone"] or None,
        created_at=at,
        expires_at=at + timedelta(hours=LINK_HOURS),
        created_by_user_id=user.id,
    )
    db.add(link_row)
    db.flush()
    from app.livewell.email_notifications import OPS_URL, render_html

    link = f"{(base_url or OPS_URL).rstrip('/')}/emergency-response/{row.id}/{token}"
    elder = db.get(Elder, row.elder_id)
    name = f"{elder.first_name} {elder.last_name}".strip() if elder else "a client"
    d = _details(row)
    body = (
        f"KushAlaya needs your help with an emergency for {name}.\n"
        f"What happened: {d.get('type_label') or 'Emergency'}.\n"
        + (f"Address: {elder.address}\n" if elder and elder.address else "")
        + (f"Message from {_name(user)}: {_clip(message, 500)}\n" if (message or "").strip() else "")
        + "Please open the link and tap Received, then On the way and Done. The link works for 48 hours."
    )
    attempts = []
    if partner["email"]:
        subject = f"KushAlaya emergency — {name}"
        attempts = inc.deliver_email(
            [partner["email"]], subject=subject, text=f"{body}\n\n{link}",
            html=render_html(f"Emergency — {name}", body, link=link, link_label="Respond"),
        )
    inc.record_notification_attempts(db, row, attempts, at=at, commit=False)
    sent = any(a.get("ok") for a in attempts)
    inc.record_event(
        db, row, "partner", channel="portal", actor_user_id=user.id, ok=sent or not partner["email"],
        detail=f"{partner['name']} notified by {_name(user)}"
        + ("" if partner["email"] else " (no email on file — call them)")
        + ("" if sent or not partner["email"] else " (email not delivered — call them)"),
        at=at,
    )
    db.commit()
    tick_step(db, row, user, "partner_notified", note=partner["name"], now=at)
    return row, link


def _link_for(db: Session, incident_id: int, token: str) -> IncidentPartnerLink:
    link_row = (
        db.query(IncidentPartnerLink)
        .filter(IncidentPartnerLink.token_hash == _hash(token or ""))
        .first()
    )
    # Same answer for a wrong token and a token for another incident.
    if not link_row or link_row.incident_id != incident_id:
        raise HTTPException(status_code=404, detail="This link is not valid")
    return link_row


def _expired(link_row: IncidentPartnerLink, at: datetime) -> bool:
    return inc._aware(link_row.expires_at) <= at


def partner_contact(tenant: Tenant | None) -> dict:
    """The agency care-team phone shown on every partner page state (tap to call)."""
    from app.livewell.care_team_contact import get_contact

    c = get_contact(tenant)
    return {"care_team_phone": c["phone"], "care_team_tel": c["phone_tel"]}


def partner_view(db: Session, incident_id: int, token: str, *, now: datetime | None = None) -> dict:
    at = now or _now()
    link_row = _link_for(db, incident_id, token)
    row = db.get(Incident, incident_id)
    elder = db.get(Elder, row.elder_id) if row else None
    expired = _expired(link_row, at)
    closed = bool(not row or row.status not in OPEN_STATUSES)
    d = _details(row) if row else {}
    # Nothing about the client once the link has expired or the emergency is closed.
    hide = expired or closed
    return {
        "partner_name": link_row.partner_name,
        "expired": expired,
        "closed": closed,
        "last_status": link_row.last_status,
        "statuses": [{"value": k, "label": v} for k, v in PARTNER_STATUSES.items()],
        "client_name": None if hide or not elder else f"{elder.first_name} {elder.last_name}".strip(),
        "address": None if hide or not elder else elder.address,
        "client_phone": None if hide or not elder else elder.phone,
        "what_happened": None if hide else d.get("type_label"),
        "opened_at": None if hide or not row else inc._aware(row.opened_at),
        **partner_contact(db.get(Tenant, link_row.tenant_id)),
    }


def partner_respond(
    db: Session, incident_id: int, token: str, status: str, note: str | None = None, *, now: datetime | None = None
) -> dict:
    at = now or _now()
    link_row = _link_for(db, incident_id, token)
    if _expired(link_row, at):
        raise HTTPException(status_code=410, detail="This link has expired")
    key = (status or "").strip().lower()
    if key not in PARTNER_STATUSES:
        raise_bad_request(f"status must be one of {', '.join(PARTNER_STATUSES)}")
    row = db.get(Incident, incident_id)
    if not row or row.status not in OPEN_STATUSES:
        raise HTTPException(status_code=410, detail="This emergency is already closed")
    link_row.last_status = key
    link_row.last_response_at = at
    text = _clip(note, 500)
    inc.record_event(
        db, row, "partner", channel="portal",
        detail=f"{link_row.partner_name}: {PARTNER_STATUSES[key]}" + (f" — {text}" if text else ""),
        at=at,
    )
    db.commit()
    return partner_view(db, incident_id, token, now=at)
