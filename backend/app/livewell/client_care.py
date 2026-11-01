"""Phase 4B: one-page client sheet (#94), care plan (#95), risk register and handovers (#98).

Who sees what
- Staff (team-scoped): everything, editable.
- Caregiver: the sheet (with keys and access) for a client they have a job with *today* (IST).
- Family: a read-only subset — never keys/access, never the risk register — plus care goals
  in plain words. Changes go through the existing "request a change" (family_my_details).

Care plan review is linked to the 6-monthly reassessment: with no review date set, the
review falls due on the reassessment due date. Marking the plan reviewed moves the next
review to the next reassessment due date (or six months on if that has passed).
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.rbac import CARE_MANAGER, SYSTEM_ADMIN, TENANT_ADMIN, assert_tenant_access
from app.core.responses import raise_bad_request, raise_not_found
from app.core.team_scope import assert_elder_in_team
from app.models.client_care import CareGoal, ClientRisk, ClientSheet, HandoverNote
from app.models.elder import Elder
from app.models.user import User

IST = timezone(timedelta(hours=5, minutes=30))
REVIEW_HEADS_UP = timedelta(days=7)
SIX_MONTHS = timedelta(days=182)

GOAL_STATUSES = ("active", "achieved", "paused", "stopped")
GOAL_WORDS = {"active": "Working on it", "achieved": "Achieved", "paused": "On hold", "stopped": "Stopped"}
RISK_LEVELS = ("low", "medium", "high")
HANDOVER_KINDS = ("shift", "client_move")
HANDOVER_TO_ROLES = (CARE_MANAGER, TENANT_ADMIN)

_PHONE_RE = re.compile(r"^\+?[0-9 ()-]{6,20}$")
TEXT_FIELDS = {
    "risks": 2000,
    "keys_access": 2000,
    "language": 120,
    "doctor_name": 200,
    "hospital_name": 200,
    "family_preferences": 2000,
}
PHONE_FIELDS = ("doctor_phone", "hospital_phone")
# Health fields kept on the elder row (family change requests point at these).
ELDER_FIELDS = {"conditions": "medical_conditions", "allergies": "allergies", "mobility": "mobility_status"}


# --- helpers -------------------------------------------------------------------------


def today_ist(now: datetime | None = None) -> date:
    return (now or datetime.now(timezone.utc)).astimezone(IST).date()


def _iso(dt) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()
    return dt.isoformat()


def _name(u: User | None) -> str:
    return f"{u.first_name or ''} {u.last_name or ''}".strip() if u else ""


def _elder_name(e: Elder) -> str:
    return f"{e.first_name} {e.last_name}".strip()


def _date(value, label: str) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise_bad_request(f"{label}: use a date like 2026-12-31")


def _phone(value, label: str) -> str:
    v = str(value or "").strip()
    if v and not _PHONE_RE.match(v):
        raise_bad_request(f"{label}: digits only, e.g. +91 98765 43210")
    return v


def staff_elder(db: Session, user: User, elder_id: int) -> Elder:
    elder = db.get(Elder, elder_id)
    if not elder:
        raise_not_found("Client not found")
    assert_tenant_access(user, elder.tenant_id)
    assert_elder_in_team(db, user, elder_id)
    return elder


def _sheet(db: Session, elder: Elder) -> ClientSheet | None:
    return db.query(ClientSheet).filter(ClientSheet.elder_id == elder.id).first()


def _sheet_or_new(db: Session, elder: Elder) -> ClientSheet:
    row = _sheet(db, elder)
    if row is None:
        row = ClientSheet(tenant_id=elder.tenant_id, elder_id=elder.id, medicines=[])
        db.add(row)
        db.flush()
    return row


def _medicines(value) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 40:
        raise_bad_request("Medicines: up to 40 rows")
    out = []
    for m in value:
        if not isinstance(m, dict):
            raise_bad_request("Medicines: each row needs a name")
        name = str(m.get("name") or "").strip()[:120]
        dose = str(m.get("dose") or "").strip()[:80]
        times = str(m.get("times") or "").strip()[:80]
        if not name:
            if dose or times:
                raise_bad_request("Medicines: each row needs a name")
            continue
        out.append({"name": name, "dose": dose, "times": times})
    return out


# --- client sheet (#94) --------------------------------------------------------------


def sheet_view(db: Session, elder: Elder, *, audience: str) -> dict:
    """audience: staff | viewer | caregiver | family.

    keys_access and open_risks go only to staff with write access (admins, care managers) and
    the caregiver on the visit day; viewers and family never get them."""
    row = _sheet(db, elder)
    attrs = elder.custom_attributes or {}
    out = {
        "elder_id": elder.id,
        "elder_name": _elder_name(elder),
        "date_of_birth": _iso(elder.date_of_birth),
        "address": elder.address or "",
        "phone": elder.phone or "",
        "emergency_contact_name": elder.emergency_contact_name or "",
        "emergency_contact_phone": elder.emergency_contact_phone or "",
        "conditions": elder.medical_conditions or "",
        "allergies": elder.allergies or "",
        "mobility": elder.mobility_status or "",
        "medicines": list(row.medicines or []) if row else [],
        "risks": (row.risks if row else "") or "",
        "language": ((row.language if row else "") or str(attrs.get("language_preference") or "")),
        "doctor_name": (row.doctor_name if row else "") or "",
        "doctor_phone": (row.doctor_phone if row else "") or "",
        "hospital_name": (row.hospital_name if row else "") or "",
        "hospital_phone": (row.hospital_phone if row else "") or "",
        "family_preferences": (row.family_preferences if row else "") or "",
        "updated_at": _iso(row.updated_at) if row else None,
    }
    if audience in ("staff", "caregiver"):
        out["keys_access"] = (row.keys_access if row else "") or ""
        out["open_risks"] = [
            {"risk": r.risk, "level": r.level, "mitigation": r.mitigation}
            for r in _risk_rows(db, elder, include_closed=False)
        ]
    if audience in ("staff", "viewer"):
        out["updated_by"] = _name(db.get(User, row.updated_by_user_id)) if row and row.updated_by_user_id else ""
    return out


def save_sheet(db: Session, user: User, elder: Elder, data: dict) -> dict:
    from sqlalchemy.orm.attributes import flag_modified

    from app.services.audit_service import AuditService

    row = _sheet_or_new(db, elder)
    changed: list[str] = []
    if "medicines" in data and data["medicines"] is not None:
        meds = _medicines(data["medicines"])
        if meds != (row.medicines or []):
            row.medicines = meds
            flag_modified(row, "medicines")
            changed.append("medicines")
    for key, limit in TEXT_FIELDS.items():
        if data.get(key) is not None:
            val = str(data[key]).strip()[:limit]
            if val != (getattr(row, key) or ""):
                setattr(row, key, val)
                changed.append(key)
    for key in PHONE_FIELDS:
        if data.get(key) is not None:
            val = _phone(data[key], "Doctor phone" if key == "doctor_phone" else "Hospital phone")
            if val != (getattr(row, key) or ""):
                setattr(row, key, val)
                changed.append(key)
    for key, col in ELDER_FIELDS.items():
        if data.get(key) is not None:
            val = str(data[key]).strip()[:2000] or None
            if val != getattr(elder, col):
                setattr(elder, col, val)
                changed.append(key)
    if changed:
        row.updated_by_user_id = user.id
        row.updated_at = datetime.now(timezone.utc)
        # Field names only: keys/access text must not be copied into the audit log.
        AuditService.log(
            db, tenant_id=elder.tenant_id, user_id=user.id, entity_type="client_sheet",
            entity_id=elder.id, action="client_sheet_updated", new_value={"fields": changed},
        )
    db.commit()
    return sheet_view(db, elder, audience="staff")


def caregiver_sheet(db: Session, user: User, job_id: int, *, now: datetime | None = None) -> dict:
    """The sheet for the client of one of the caregiver's jobs, on the day of the visit only."""
    from app.core.rbac import CAREGIVER
    from app.livewell.care_jobs import _aware, _caregiver_job

    job = _caregiver_job(db, user, job_id)
    if user.role == CAREGIVER:
        from app.livewell.care_jobs import caregiver_inactive
        from app.models.caregiver import Caregiver

        if caregiver_inactive(db.get(Caregiver, user.caregiver_id)):
            raise_not_found("Job not found")  # a caregiver who has left no longer sees client details
        live = job.status in ("on_the_way", "checked_in")
        on_day = job.scheduled_at is not None and today_ist(_aware(job.scheduled_at)) == today_ist(now)
        if job.status == "cancelled" or not (live or on_day):
            raise_not_found("The client sheet opens on the day of the visit")
    elder = db.get(Elder, job.elder_id)
    if not elder:
        raise_not_found("Client not found")
    return sheet_view(db, elder, audience="caregiver")


# --- care plan (#95) ------------------------------------------------------------------


def _goal_dict(g: CareGoal, *, family: bool = False) -> dict:
    d = {
        "id": g.id,
        "goal": g.goal,
        "target_date": _iso(g.target_date),
        "status": g.status,
        "status_label": GOAL_WORDS.get(g.status, g.status),
        "interventions": list(g.interventions or []),
        "progress": g.progress or "",
        "updated_at": _iso(g.updated_at),
    }
    if not family:
        d["sort_order"] = g.sort_order
    return d


def _goals(db: Session, elder: Elder) -> list[CareGoal]:
    return (
        db.query(CareGoal)
        .filter(CareGoal.elder_id == elder.id)
        .order_by(CareGoal.sort_order, CareGoal.id)
        .all()
    )


def review_info(db: Session, elder: Elder, *, now: datetime | None = None) -> dict:
    from app.livewell.reassessment import due_info

    today = today_ist(now)
    row = _sheet(db, elder)
    reassess = due_info(db, elder, now=now)
    set_date = row.care_plan_review_date if row else None
    reassess_date = (
        datetime.fromisoformat(reassess["due_at"]).astimezone(IST).date() if reassess.get("due_at") else None
    )
    review = set_date or reassess_date
    return {
        "review_date": _iso(review),
        "source": "set" if set_date else ("reassessment" if reassess_date else None),
        "reviewed_at": _iso(row.care_plan_reviewed_at) if row else None,
        "due": bool(review and review - today <= REVIEW_HEADS_UP),
        "overdue": bool(review and review < today),
        "reassessment": reassess,
    }


def care_plan_view(db: Session, elder: Elder) -> dict:
    return {"goals": [_goal_dict(g) for g in _goals(db, elder)], "review": review_info(db, elder)}


def _goal_fields(g: CareGoal, data: dict) -> None:
    if data.get("goal") is not None:
        text = str(data["goal"]).strip()[:1000]
        if not text:
            raise_bad_request("Write the goal")
        g.goal = text
    if "target_date" in data:
        g.target_date = _date(data["target_date"], "Target date")
    if data.get("status") is not None:
        if data["status"] not in GOAL_STATUSES:
            raise_bad_request("Status: active, achieved, paused or stopped")
        g.status = data["status"]
    if data.get("interventions") is not None:
        items = data["interventions"]
        if not isinstance(items, list) or len(items) > 20:
            raise_bad_request("Up to 20 things we do for each goal")
        g.interventions = [str(i).strip()[:300] for i in items if str(i).strip()]
    if data.get("progress") is not None:
        g.progress = str(data["progress"]).strip()[:2000]
    if data.get("sort_order") is not None:
        g.sort_order = int(data["sort_order"])


def create_goal(db: Session, user: User, elder: Elder, data: dict) -> dict:
    if not str(data.get("goal") or "").strip():
        raise_bad_request("Write the goal")
    g = CareGoal(tenant_id=elder.tenant_id, elder_id=elder.id, created_by_user_id=user.id, interventions=[])
    _goal_fields(g, {"status": "active", **data})
    db.add(g)
    db.commit()
    return _goal_dict(g)


def _goal_for(db: Session, elder: Elder, goal_id: int) -> CareGoal:
    g = db.get(CareGoal, goal_id)
    if not g or g.elder_id != elder.id:
        raise_not_found("Goal not found")
    return g


def update_goal(db: Session, elder: Elder, goal_id: int, data: dict) -> dict:
    g = _goal_for(db, elder, goal_id)
    _goal_fields(g, data)
    db.commit()
    return _goal_dict(g)


def delete_goal(db: Session, elder: Elder, goal_id: int) -> dict:
    db.delete(_goal_for(db, elder, goal_id))
    db.commit()
    return {"ok": True}


def set_review(db: Session, user: User, elder: Elder, data: dict, *, now: datetime | None = None) -> dict:
    """reviewed=true marks it reviewed now; review_date sets the next one (else the next
    reassessment due date, or six months on)."""
    row = _sheet_or_new(db, elder)
    now = now or datetime.now(timezone.utc)
    if data.get("reviewed"):
        row.care_plan_reviewed_at = now
        nxt = _date(data.get("review_date"), "Next review")
        if nxt is None:
            info = review_info(db, elder, now=now)["reassessment"]
            due = datetime.fromisoformat(info["due_at"]).astimezone(IST).date() if info.get("due_at") else None
            nxt = due if due and due > today_ist(now) + REVIEW_HEADS_UP else today_ist(now) + SIX_MONTHS
        row.care_plan_review_date = nxt
    elif "review_date" in data:
        row.care_plan_review_date = _date(data.get("review_date"), "Review date")
    row.updated_by_user_id = user.id
    db.commit()
    return care_plan_view(db, elder)


def family_care_view(db: Session, user: User) -> dict:
    """Family: read-only sheet subset (no keys/access, no risk register) and goals in plain words."""
    from app.services.elder_portal_service import ElderPortalService

    elder = ElderPortalService.get_linked_elder(db, user)
    info = review_info(db, elder)
    return {
        "sheet": sheet_view(db, elder, audience="family"),
        "goals": [_goal_dict(g, family=True) for g in _goals(db, elder) if g.status != "stopped"],
        "next_review": info["review_date"],
    }


def review_due_list(db: Session, elders: list[Elder], *, now: datetime | None = None) -> list[dict]:
    """Dashboard: clients with active goals whose care plan review is due within a week or overdue."""
    ids = {
        r[0]
        for r in db.query(CareGoal.elder_id)
        .filter(CareGoal.elder_id.in_([e.id for e in elders] or [-1]), CareGoal.status == "active")
        .distinct()
        .all()
    }
    out = []
    for e in elders:
        if e.id not in ids:
            continue
        info = review_info(db, e, now=now)
        if info["due"]:
            out.append({
                "elder_id": e.id,
                "elder_name": _elder_name(e),
                "review_date": info["review_date"],
                "overdue": info["overdue"],
                "source": info["source"],
            })
    out.sort(key=lambda r: (not r["overdue"], r["review_date"] or ""))
    return out


# --- risk register (#98) --------------------------------------------------------------


def _risk_rows(db: Session, elder: Elder, *, include_closed: bool) -> list[ClientRisk]:
    q = db.query(ClientRisk).filter(ClientRisk.elder_id == elder.id)
    if not include_closed:
        q = q.filter(ClientRisk.status == "open")
    rows = q.all()
    order = {"high": 0, "medium": 1, "low": 2}
    rows.sort(key=lambda r: (r.status != "open", order.get(r.level, 3), r.id))
    return rows


def _risk_dict(db: Session, r: ClientRisk, today: date) -> dict:
    return {
        "id": r.id,
        "risk": r.risk,
        "level": r.level,
        "mitigation": r.mitigation or "",
        "owner_user_id": r.owner_user_id,
        "owner_name": _name(db.get(User, r.owner_user_id)) if r.owner_user_id else "",
        "review_date": _iso(r.review_date),
        "review_overdue": bool(r.status == "open" and r.review_date and r.review_date < today),
        "status": r.status,
        "updated_at": _iso(r.updated_at),
    }


def list_risks(db: Session, elder: Elder) -> list[dict]:
    today = today_ist()
    return [_risk_dict(db, r, today) for r in _risk_rows(db, elder, include_closed=True)]


def _owner(db: Session, elder: Elder, owner_id) -> int | None:
    if owner_id in (None, ""):
        return None
    u = db.get(User, int(owner_id))
    if not u or u.tenant_id != elder.tenant_id:
        raise_bad_request("Owner must be someone in your organisation")
    return u.id


def _risk_fields(db: Session, elder: Elder, r: ClientRisk, data: dict) -> None:
    if data.get("risk") is not None:
        text = str(data["risk"]).strip()[:300]
        if not text:
            raise_bad_request("Describe the risk")
        r.risk = text
    if data.get("level") is not None:
        if data["level"] not in RISK_LEVELS:
            raise_bad_request("Level: low, medium or high")
        r.level = data["level"]
    if data.get("mitigation") is not None:
        r.mitigation = str(data["mitigation"]).strip()[:2000]
    if "owner_user_id" in data:
        r.owner_user_id = _owner(db, elder, data["owner_user_id"])
    if "review_date" in data:
        r.review_date = _date(data["review_date"], "Review date")
    if data.get("status") is not None:
        if data["status"] not in ("open", "closed"):
            raise_bad_request("Status: open or closed")
        r.status = data["status"]


def create_risk(db: Session, user: User, elder: Elder, data: dict) -> dict:
    if not str(data.get("risk") or "").strip():
        raise_bad_request("Describe the risk")
    r = ClientRisk(tenant_id=elder.tenant_id, elder_id=elder.id, status="open", level="medium",
                   owner_user_id=user.id)
    _risk_fields(db, elder, r, data)
    db.add(r)
    db.commit()
    return _risk_dict(db, r, today_ist())


def update_risk(db: Session, elder: Elder, risk_id: int, data: dict) -> dict:
    r = db.get(ClientRisk, risk_id)
    if not r or r.elder_id != elder.id:
        raise_not_found("Risk not found")
    _risk_fields(db, elder, r, data)
    db.commit()
    return _risk_dict(db, r, today_ist())


def risk_flags(db: Session, elders: list[Elder], *, now: datetime | None = None) -> list[dict]:
    """Dashboard: open high risks, and open risks whose review date has passed."""
    today = today_ist(now)
    names = {e.id: _elder_name(e) for e in elders}
    rows = (
        db.query(ClientRisk)
        .filter(ClientRisk.elder_id.in_(list(names) or [-1]), ClientRisk.status == "open")
        .all()
    )
    out = []
    for r in rows:
        overdue = bool(r.review_date and r.review_date < today)
        if r.level != "high" and not overdue:
            continue
        out.append({
            "id": r.id,
            "elder_id": r.elder_id,
            "elder_name": names.get(r.elder_id, ""),
            "risk": r.risk,
            "level": r.level,
            "review_date": _iso(r.review_date),
            "review_overdue": overdue,
        })
    out.sort(key=lambda f: (f["level"] != "high", not f["review_overdue"], f["elder_name"]))
    return out


# --- handovers (#98) -----------------------------------------------------------------


def _handover_dict(db: Session, h: HandoverNote) -> dict:
    elder = db.get(Elder, h.elder_id) if h.elder_id else None
    return {
        "id": h.id,
        "kind": h.kind,
        "kind_label": "Client moved" if h.kind == "client_move" else "Shift handover",
        "elder_id": h.elder_id,
        "elder_name": _elder_name(elder) if elder else "",
        "from_user_id": h.from_user_id,
        "from_name": _name(db.get(User, h.from_user_id)) if h.from_user_id else "",
        "to_user_id": h.to_user_id,
        "to_name": _name(db.get(User, h.to_user_id)),
        "note": h.note,
        "created_at": _iso(h.created_at),
        "acknowledged_at": _iso(h.acknowledged_at),
    }


def handover_recipients(db: Session, user: User) -> list[dict]:
    tid = user.tenant_id
    q = db.query(User).filter(User.role.in_(HANDOVER_TO_ROLES), User.id != user.id)
    if tid is not None:
        q = q.filter(User.tenant_id == tid)
    q = q.filter(User.status == "ACTIVE")
    return [{"id": u.id, "name": _name(u) or u.email, "role": u.role} for u in q.order_by(User.first_name).all()]


def create_handover(db: Session, user: User, data: dict) -> dict:
    from app.services.audit_service import AuditService

    kind = data.get("kind") or "shift"
    if kind not in HANDOVER_KINDS:
        raise_bad_request("Kind: shift or client_move")
    note = str(data.get("note") or "").strip()[:4000]
    if not note:
        raise_bad_request("Write the handover note")
    to = db.get(User, int(data.get("to_user_id") or 0))
    if not to or to.id == user.id or to.role not in HANDOVER_TO_ROLES or to.status != "ACTIVE" or (
        user.tenant_id is not None and to.tenant_id != user.tenant_id
    ):
        raise_bad_request("Choose the manager receiving the handover")
    elder = None
    if data.get("elder_id"):
        elder = staff_elder(db, user, int(data["elder_id"]))
    if kind == "client_move" and elder is None:
        raise_bad_request("Choose the client who is moving")
    tenant_id = elder.tenant_id if elder else (user.tenant_id or to.tenant_id)
    h = HandoverNote(tenant_id=tenant_id, elder_id=elder.id if elder else None, kind=kind,
                     from_user_id=user.id, to_user_id=to.id, note=note)
    db.add(h)
    if kind == "client_move":
        old = elder.manager_user_id
        elder.manager_user_id = to.id
        AuditService.log(
            db, tenant_id=elder.tenant_id, user_id=user.id, entity_type="elder", entity_id=elder.id,
            action="client_manager_changed", old_value={"manager_user_id": old},
            new_value={"manager_user_id": to.id},
        )
    db.commit()
    return _handover_dict(db, h)


def list_handovers(db: Session, user: User, *, box: str = "inbox", elder: Elder | None = None) -> list[dict]:
    q = db.query(HandoverNote)
    if elder is not None:
        q = q.filter(HandoverNote.elder_id == elder.id)
    else:
        if user.tenant_id is not None:
            q = q.filter(HandoverNote.tenant_id == user.tenant_id)
        if box == "sent":
            q = q.filter(HandoverNote.from_user_id == user.id)
        elif box == "all" and user.role in (TENANT_ADMIN, SYSTEM_ADMIN):
            pass
        else:
            q = q.filter(HandoverNote.to_user_id == user.id)
    rows = q.order_by(HandoverNote.created_at.desc(), HandoverNote.id.desc()).limit(100).all()
    return [_handover_dict(db, h) for h in rows]


def acknowledge_handover(db: Session, user: User, handover_id: int) -> dict:
    h = db.get(HandoverNote, handover_id)
    if not h or h.to_user_id != user.id:
        raise_not_found("Handover not found")
    if h.acknowledged_at is None:
        h.acknowledged_at = datetime.now(timezone.utc)
        db.commit()
    return _handover_dict(db, h)


def pending_handovers(db: Session, user: User) -> list[dict]:
    rows = (
        db.query(HandoverNote)
        .filter(HandoverNote.to_user_id == user.id, HandoverNote.acknowledged_at.is_(None))
        .order_by(HandoverNote.created_at)
        .all()
    )
    return [_handover_dict(db, h) for h in rows]
