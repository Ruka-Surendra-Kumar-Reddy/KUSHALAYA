"""A client's care team: the care manager and the regular caregivers.

No new tables. The care manager is ``Elder.manager_user_id`` (changed through the
existing client-move handover); regular caregivers are ACTIVE ``Assignment`` rows.
Removing a caregiver ends the assignment (INACTIVE + end date) so history stays.
Replacing one can also move this client's upcoming visits and repeating visits
(existing bulk reassign + series change), with clashes reported, not skipped.
Every change is written to the audit log and shown as "Recent changes".
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.rbac import ADMIN_ROLES, CARE_MANAGER
from app.core.responses import raise_bad_request, raise_not_found
from app.livewell import care_jobs
from app.livewell import client_care as cc
from app.models.assignment import Assignment
from app.models.audit_log import AuditLog
from app.models.care_job import CareJob
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.user import User

IST = cc.IST
ACTIONS = (
    "client_manager_changed",
    "care_team_caregiver_added",
    "care_team_caregiver_replaced",
    "care_team_caregiver_removed",
)


def is_admin(user: User) -> bool:
    return user.role in ADMIN_ROLES


def staff_elder(db: Session, user: User, elder_id: int) -> Elder:
    return care_jobs._elder_for(db, user, elder_id)


def _uname(u: User | None) -> str:
    return (f"{u.first_name or ''} {u.last_name or ''}".strip() or u.email) if u else ""


def _cname(cg: Caregiver | None) -> str:
    return care_jobs._name(cg.first_name, cg.last_name) if cg else ""


def _ist_label(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    d = dt.astimezone(IST)
    return f"{d.day} {d.strftime('%b %Y')}, {d.strftime('%I:%M').lstrip('0')} {d.strftime('%p').lower()}"


def _audit(db: Session, user: User, elder: Elder, action: str, old: dict | None, new: dict | None) -> None:
    from app.services.audit_service import AuditService

    AuditService.log(
        db, tenant_id=elder.tenant_id, user_id=user.id, entity_type="elder", entity_id=elder.id,
        action=action, old_value=old, new_value=new,
    )


def _active(db: Session, elder: Elder) -> list[Assignment]:
    return (
        db.query(Assignment)
        .filter(Assignment.elder_id == elder.id, Assignment.status == "ACTIVE")
        .order_by(Assignment.start_date, Assignment.id)
        .all()
    )


def _assignment(db: Session, elder: Elder, assignment_id: int) -> Assignment:
    a = db.get(Assignment, assignment_id)
    if not a or a.elder_id != elder.id or a.status != "ACTIVE":
        raise_not_found("Caregiver not on this client's care team")
    return a


# --- read --------------------------------------------------------------------------


def _describe(row: AuditLog, users: dict[int, User]) -> str:
    old, new = row.old_value or {}, row.new_value or {}
    if row.action == "client_manager_changed":
        before = _uname(users.get(old.get("manager_user_id")))
        after = _uname(users.get(new.get("manager_user_id"))) or "nobody"
        return f"Care manager changed to {after}" + (f" (was {before})" if before else "")
    if row.action == "care_team_caregiver_added":
        return f"{new.get('caregiver_name') or 'Caregiver'} added as caregiver"
    if row.action == "care_team_caregiver_removed":
        return f"{old.get('caregiver_name') or 'Caregiver'} removed as caregiver"
    if row.action == "care_team_caregiver_replaced":
        text = f"{old.get('caregiver_name') or 'Caregiver'} replaced by {new.get('caregiver_name') or 'caregiver'}"
        if new.get("moved_visits"):
            text += f"; {new.get('moved_visits')} upcoming visit(s) moved"
        return text
    return row.action


def recent_changes(db: Session, elder: Elder, limit: int = 10) -> list[dict]:
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "elder", AuditLog.entity_id == elder.id, AuditLog.action.in_(ACTIONS))
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .limit(limit)
        .all()
    )
    ids = {r.user_id for r in rows if r.user_id}
    for r in rows:
        if r.action == "client_manager_changed":
            ids |= {v for v in ((r.old_value or {}).get("manager_user_id"), (r.new_value or {}).get("manager_user_id")) if v}
    users = {u.id: u for u in db.query(User).filter(User.id.in_(ids)).all()} if ids else {}
    return [
        {
            "id": r.id,
            "action": r.action,
            "what": _describe(r, users),
            "who": _uname(users.get(r.user_id)) or "System",
            "at": (r.timestamp.replace(tzinfo=timezone.utc) if r.timestamp and r.timestamp.tzinfo is None else r.timestamp).isoformat() if r.timestamp else None,
            "at_label": _ist_label(r.timestamp),
        }
        for r in rows
    ]


def care_team(db: Session, user: User, elder: Elder) -> dict:
    m = db.get(User, elder.manager_user_id) if elder.manager_user_id else None
    rows = _active(db, elder)
    cg_ids = [a.caregiver_id for a in rows]
    cgs = {c.id: c for c in db.query(Caregiver).filter(Caregiver.id.in_(cg_ids)).all()} if cg_ids else {}
    nexts = {}
    if cg_ids:
        nexts = dict(
            db.query(CareJob.caregiver_id, func.min(CareJob.scheduled_at))
            .filter(
                CareJob.elder_id == elder.id,
                CareJob.caregiver_id.in_(cg_ids),
                CareJob.status.in_(care_jobs.OPEN_STATUSES),
                CareJob.scheduled_at >= datetime.now(timezone.utc),
            )
            .group_by(CareJob.caregiver_id)
            .all()
        )
    caregivers = []
    for a in rows:
        cg = cgs.get(a.caregiver_id)
        nv = care_jobs._aware(nexts.get(a.caregiver_id))
        caregivers.append(
            {
                "assignment_id": a.id,
                "caregiver_id": a.caregiver_id,
                "name": _cname(cg),
                "phone": cg.phone if cg else None,
                "since": a.start_date.isoformat() if a.start_date else None,
                "next_visit_at": nv.isoformat() if nv else None,
            }
        )
    return {
        "elder_id": elder.id,
        "manager": (
            {"id": m.id, "name": _uname(m), "email": m.email, "phone": getattr(m, "phone", None)} if m else None
        ),
        "caregivers": caregivers,
        "recent_changes": recent_changes(db, elder),
        "can_change_manager": is_admin(user),
        "can_edit_caregivers": user.role in (*ADMIN_ROLES, CARE_MANAGER),
    }


def caregiver_clients(db: Session, user: User, caregiver_id: int) -> list[dict]:
    """"Their clients" on a caregiver's profile: ACTIVE assignments, team-scoped."""
    from app.core.team_scope import team_elder_ids

    rows = (
        db.query(Assignment, Elder)
        .join(Elder, Elder.id == Assignment.elder_id)
        .filter(Assignment.caregiver_id == caregiver_id, Assignment.status == "ACTIVE")
        .order_by(Elder.first_name)
        .all()
    )
    scope = team_elder_ids(db, user)
    return [
        {
            "assignment_id": a.id,
            "elder_id": e.id,
            "name": cc._elder_name(e),
            "since": a.start_date.isoformat() if a.start_date else None,
        }
        for a, e in rows
        if scope is None or e.id in scope
    ]


# --- care manager ------------------------------------------------------------------


def _notify_manager(db: Session, elder: Elder, to: User, by: User, note: str) -> None:
    try:
        from app.livewell.email_notifications import email_context, send, staff_path

        name = cc._elder_name(elder)
        with email_context(staff_path(elder), name):
            send(
                [to.email],
                f"You are now {name}'s care manager",
                f"{_uname(by)} made you the care manager for {name}.\n\nHandover note: {note}",
                family=False,
            )
    except Exception:  # email is best-effort; the handover note is the record
        pass


def set_manager(db: Session, user: User, elder: Elder, manager_user_id: int, note: str | None) -> dict:
    to = db.get(User, int(manager_user_id or 0))
    if not to or to.role != CARE_MANAGER or to.status != "ACTIVE" or to.tenant_id != elder.tenant_id:
        raise_bad_request("Choose an active care manager")
    if elder.manager_user_id == to.id:
        raise_bad_request(f"{_uname(to)} is already the care manager")
    text = (note or "").strip() or f"{cc._elder_name(elder)} is now in your care team."
    cc.create_handover(
        db, user, {"kind": "client_move", "to_user_id": to.id, "elder_id": elder.id, "note": text}
    )
    _notify_manager(db, elder, to, user, text)
    db.refresh(elder)
    return care_team(db, user, elder)


# --- caregivers --------------------------------------------------------------------


def add_caregiver(db: Session, user: User, elder: Elder, caregiver_id: int, *, commit: bool = True) -> dict:
    cg = care_jobs._caregiver_for(db, user, elder, int(caregiver_id or 0))
    if any(a.caregiver_id == cg.id for a in _active(db, elder)):
        raise_bad_request(f"{cg.first_name} is already on the care team")
    db.add(
        Assignment(
            tenant_id=elder.tenant_id, elder_id=elder.id, caregiver_id=cg.id,
            start_date=cc.today_ist(), status="ACTIVE",
        )
    )
    _audit(db, user, elder, "care_team_caregiver_added", None, {"caregiver_id": cg.id, "caregiver_name": _cname(cg)})
    if commit:
        db.commit()
        return care_team(db, user, elder)
    return {}


def remove_caregiver(db: Session, user: User, elder: Elder, assignment_id: int) -> dict:
    a = _assignment(db, elder, assignment_id)
    cg = db.get(Caregiver, a.caregiver_id)
    a.status = "INACTIVE"
    a.end_date = cc.today_ist()
    _audit(db, user, elder, "care_team_caregiver_removed", {"caregiver_id": a.caregiver_id, "caregiver_name": _cname(cg)}, None)
    db.commit()
    return care_team(db, user, elder)


def _move_visits(db: Session, user: User, elder: Elder, old_id: int, new_id: int) -> tuple[int, list[dict], bool]:
    """Repeating visits (split from the next visit on) and then any other upcoming
    visits. Returns (moved count, clashes, family already told)."""
    from app.livewell import care_series
    from app.livewell.leave_cover import MOVABLE, bulk_reassign
    from app.models.care_series import CareSeries

    clashes: list[dict] = []
    moved = 0
    told = False
    today = cc.today_ist()
    for s in (
        db.query(CareSeries)
        .filter(CareSeries.elder_id == elder.id, CareSeries.status == "active", CareSeries.caregiver_id == old_id)
        .all()
    ):
        nxt = (
            db.query(CareJob)
            .filter(CareJob.series_id == s.id, CareJob.status == "scheduled", CareJob.series_date >= today)
            .order_by(CareJob.series_date)
            .first()
        )
        if nxt is None:
            s.caregiver_id = new_id
            db.commit()
            continue
        res = care_series.change_series(
            db, user, s.id, {"scope": "following", "job_id": nxt.id, "caregiver_id": new_id}
        )
        told = True
        moved += int(res.get("created") or 0)
        clashes += [
            {"job_id": c.get("job_id"), "date": c.get("date"), "reason": c.get("reason")} for c in res.get("clashes") or []
        ]
    ids = [
        j.id
        for j in db.query(CareJob.id)
        .filter(
            CareJob.elder_id == elder.id,
            CareJob.caregiver_id == old_id,
            CareJob.status.in_(MOVABLE),
            CareJob.scheduled_at >= datetime.now(timezone.utc),
        )
        .all()
    ]
    if ids:
        res = bulk_reassign(db, user, ids, new_id)
        moved += len(res["moved"])
        told = told or bool(res["moved"])
        for f in res["failed"]:
            job = db.get(CareJob, f["job_id"])
            when = care_jobs._aware(job.scheduled_at) if job and job.scheduled_at else None
            clashes.append(
                {"job_id": f["job_id"], "date": when.astimezone(IST).date().isoformat() if when else None, "reason": f["reason"]}
            )
    return moved, clashes, told


def replace_caregiver(
    db: Session, user: User, elder: Elder, assignment_id: int, caregiver_id: int, *, move_visits: bool = False
) -> dict:
    a = _assignment(db, elder, assignment_id)
    new = care_jobs._caregiver_for(db, user, elder, int(caregiver_id or 0))
    if new.id == a.caregiver_id:
        raise_bad_request(f"{new.first_name} is already this caregiver")
    old = db.get(Caregiver, a.caregiver_id)
    a.status = "INACTIVE"
    a.end_date = cc.today_ist()
    if not any(x.caregiver_id == new.id for x in _active(db, elder) if x.id != a.id):
        db.add(
            Assignment(
                tenant_id=elder.tenant_id, elder_id=elder.id, caregiver_id=new.id,
                start_date=cc.today_ist(), status="ACTIVE",
            )
        )
    db.commit()
    moved, clashes, told = (0, [], False)
    if move_visits:
        moved, clashes, told = _move_visits(db, user, elder, old.id, new.id)
    if not told:
        care_jobs._notify_family(
            db, elder, "Change of caregiver",
            f"{new.first_name} will be {elder.first_name}'s regular caregiver instead of {old.first_name if old else 'before'}.",
        )
    _audit(
        db, user, elder, "care_team_caregiver_replaced",
        {"caregiver_id": old.id if old else None, "caregiver_name": _cname(old)},
        {"caregiver_id": new.id, "caregiver_name": _cname(new), "move_visits": move_visits,
         "moved_visits": moved, "clashes": len(clashes)},
    )
    db.commit()
    out = care_team(db, user, elder)
    out["moved_visits"] = moved
    out["clashes"] = clashes
    return out


# --- bulk (clients list) -----------------------------------------------------------


def bulk(db: Session, user: User, elder_ids: list[int], *, action: str, manager_user_id=None, caregiver_id=None, note=None) -> dict:
    from fastapi import HTTPException
    from workforceos_core.exceptions import WorkforceHTTPError

    if action not in ("manager", "caregiver"):
        raise_bad_request("Action: manager or caregiver")
    if not elder_ids:
        raise_bad_request("Pick at least one client")
    done, failed = [], []
    for eid in dict.fromkeys(int(x) for x in elder_ids):
        name = ""
        try:
            elder = staff_elder(db, user, eid)
            name = cc._elder_name(elder)
            if action == "manager":
                set_manager(db, user, elder, manager_user_id, note)
            else:
                add_caregiver(db, user, elder, caregiver_id)
            done.append({"elder_id": eid, "name": name})
        except (HTTPException, WorkforceHTTPError) as exc:
            # Validation fails before anything is written, so there is nothing to undo.
            failed.append({"elder_id": eid, "name": name, "reason": str(exc.detail)})
    return {"done": done, "failed": failed}
