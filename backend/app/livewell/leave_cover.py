"""Leave and cover (FIX_TODO 96).

Caregiver leave uses the existing LeaveRequest model and LeaveService (request →
approve/reject). On top of it: team scope, the visits a leave affects, "Find
cover" suggestions (no clash, same team first) and bulk reassignment, with the
family told about the change of caregiver.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.rbac import CAREGIVER, assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.core.team_scope import assert_caregiver_in_team, team_caregiver_ids
from app.livewell import care_jobs
from app.livewell.care_jobs import IST, OPEN_STATUSES, _aware, _name
from app.livewell.care_series import INACTIVE_CAREGIVER, clash_reason
from app.models.assignment import Assignment
from app.models.care_job import CareJob
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.leave_request import LeaveRequest
from app.models.user import User
from app.services.leave_service import LeaveService

MOVABLE = ("requested", "scheduled")


def _leave_row(db: Session, user: User, leave_id: int) -> LeaveRequest:
    row = db.get(LeaveRequest, leave_id)
    if not row:
        raise_not_found("Leave request not found")
    assert_tenant_access(user, row.tenant_id)
    assert_caregiver_in_team(db, user, row.caregiver_id)
    return row


def _staff_caregiver(db: Session, user: User, caregiver_id: int) -> Caregiver:
    cg = db.get(Caregiver, caregiver_id)
    if not cg:
        raise_not_found("Caregiver not found")
    assert_tenant_access(user, cg.tenant_id)
    assert_caregiver_in_team(db, user, cg.id)
    return cg


def _jobs_in_leave(db: Session, row: LeaveRequest) -> list[CareJob]:
    start = datetime.combine(row.start_date, time(0, 0), tzinfo=IST).astimezone(timezone.utc)
    end = datetime.combine(row.end_date + timedelta(days=1), time(0, 0), tzinfo=IST).astimezone(timezone.utc)
    return (
        db.query(CareJob)
        .filter(
            CareJob.caregiver_id == row.caregiver_id,
            CareJob.status.in_(OPEN_STATUSES),
            CareJob.scheduled_at >= start,
            CareJob.scheduled_at < end,
        )
        .order_by(CareJob.scheduled_at)
        .all()
    )


def affected_visits(db: Session, user: User, leave_id: int) -> list[dict]:
    row = _leave_row(db, user, leave_id)
    return [care_jobs.serialize(db, j) for j in _jobs_in_leave(db, row)]


COVER_STATUSES = ("requested", "scheduled", "on_the_way")


def needs_cover(db: Session, elder_ids, *, now: datetime | None = None) -> list[dict]:
    """Visits (today onwards) whose caregiver is on APPROVED leave that day — "Visit needs cover".

    ``elder_ids`` limits to the viewer's clients (dashboard / badge team scope).
    """
    now = now or datetime.now(timezone.utc)
    ids = list(elder_ids or []) or [-1]
    today = now.astimezone(IST).date()
    leaves = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.status == "APPROVED", LeaveRequest.end_date >= today)
        .all()
    )
    if not leaves:
        return []
    out: list[dict] = []
    seen: set[int] = set()
    day_start = datetime.combine(today, time(0, 0), tzinfo=IST).astimezone(timezone.utc)
    for lv in leaves:
        start = datetime.combine(max(lv.start_date, today), time(0, 0), tzinfo=IST).astimezone(timezone.utc)
        end = datetime.combine(lv.end_date + timedelta(days=1), time(0, 0), tzinfo=IST).astimezone(timezone.utc)
        jobs = (
            db.query(CareJob)
            .filter(
                CareJob.caregiver_id == lv.caregiver_id,
                CareJob.elder_id.in_(ids),
                CareJob.status.in_(COVER_STATUSES),
                CareJob.scheduled_at >= max(start, day_start),
                CareJob.scheduled_at < end,
            )
            .all()
        )
        if not jobs:
            continue
        cg = db.get(Caregiver, lv.caregiver_id)
        cg_name = _name(cg.first_name, cg.last_name) if cg else ""
        for j in jobs:
            if j.id in seen:
                continue
            seen.add(j.id)
            e = db.get(Elder, j.elder_id)
            out.append(
                {
                    "job_id": j.id,
                    "elder_id": j.elder_id,
                    "elder_name": _name(e.first_name, e.last_name) if e else "",
                    "title": j.title,
                    "kind": j.kind,
                    "at": _aware(j.scheduled_at).isoformat(),
                    "caregiver_id": lv.caregiver_id,
                    "caregiver_name": cg_name,
                    "leave_id": lv.id,
                }
            )
    out.sort(key=lambda r: r["at"])
    return out


def _with_counts(db: Session, row_dict: dict, row: LeaveRequest) -> dict:
    out = dict(row_dict)
    for k in ("start_date", "end_date", "resolved_at", "created_at"):
        v = out.get(k)
        if isinstance(v, (date, datetime)):
            out[k] = v.isoformat()
    out["affected_count"] = len(_jobs_in_leave(db, row)) if row.status in ("PENDING", "APPROVED") else 0
    return out


def list_leave(
    db: Session,
    user: User,
    *,
    status: str | None = None,
    start: date | None = None,
    end: date | None = None,
    caregiver_id: int | None = None,
) -> list[dict]:
    q = db.query(LeaveRequest)
    tid = resolve_tenant_id(user)
    if tid is not None:
        q = q.filter(LeaveRequest.tenant_id == tid)
    team = team_caregiver_ids(db, user)
    if team is not None:
        q = q.filter(LeaveRequest.caregiver_id.in_(team or {-1}))
    if caregiver_id is not None:
        q = q.filter(LeaveRequest.caregiver_id == caregiver_id)
    if status:
        q = q.filter(LeaveRequest.status == status.upper())
    if start is not None:
        q = q.filter(LeaveRequest.end_date >= start)
    if end is not None:
        q = q.filter(LeaveRequest.start_date <= end)
    rows = q.order_by(LeaveRequest.start_date.desc(), LeaveRequest.id.desc()).limit(300).all()
    return [_with_counts(db, LeaveService._to_dict(db, r), r) for r in rows]


def staff_request(db: Session, user: User, data: dict) -> dict:
    """A manager records leave for a caregiver (optionally approving it at once)."""
    cg = _staff_caregiver(db, user, int(data["caregiver_id"]))
    out = LeaveService.create(
        db,
        cg,
        leave_type=data.get("leave_type") or "ANNUAL",
        start_date=data["start_date"],
        end_date=data["end_date"],
        reason=data.get("reason"),
        actor=user,
    )
    if data.get("approve"):
        return approve(db, user, out["id"])
    row = db.get(LeaveRequest, out["id"])
    return {"leave": _with_counts(db, out, row), "affected": []}


def approve(db: Session, user: User, leave_id: int) -> dict:
    _leave_row(db, user, leave_id)
    out = LeaveService.approve(db, leave_id, user)
    row = db.get(LeaveRequest, leave_id)
    return {"leave": _with_counts(db, out, row), "affected": [care_jobs.serialize(db, j) for j in _jobs_in_leave(db, row)]}


def reject(db: Session, user: User, leave_id: int, reason: str | None) -> dict:
    _leave_row(db, user, leave_id)
    out = LeaveService.reject(db, leave_id, user, reason)
    row = db.get(LeaveRequest, leave_id)
    return {"leave": _with_counts(db, out, row)}


# --- caregiver app ---------------------------------------------------------------


def _own_caregiver(db: Session, user: User) -> Caregiver:
    if user.role != CAREGIVER or not user.caregiver_id:
        raise_bad_request("Only caregivers can request leave here")
    cg = db.get(Caregiver, user.caregiver_id)
    if not cg:
        raise_not_found("Caregiver not found")
    return cg


def caregiver_list(db: Session, user: User) -> list[dict]:
    cg = _own_caregiver(db, user)
    rows = (
        db.query(LeaveRequest)
        .filter(LeaveRequest.caregiver_id == cg.id)
        .order_by(LeaveRequest.start_date.desc())
        .limit(50)
        .all()
    )
    out = []
    for r in rows:
        d = LeaveService._to_dict(db, r)
        out.append({k: (v.isoformat() if isinstance(v, (date, datetime)) else v) for k, v in d.items()})
    return out


def caregiver_request(db: Session, user: User, data: dict) -> dict:
    cg = _own_caregiver(db, user)
    d = LeaveService.create(
        db,
        cg,
        leave_type=data.get("leave_type") or "ANNUAL",
        start_date=data["start_date"],
        end_date=data["end_date"],
        reason=data.get("reason"),
        actor=user,
    )
    return {k: (v.isoformat() if isinstance(v, (date, datetime)) else v) for k, v in d.items()}


def caregiver_cancel(db: Session, user: User, leave_id: int) -> dict:
    cg = _own_caregiver(db, user)
    d = LeaveService.cancel(db, leave_id, cg, user)
    return {k: (v.isoformat() if isinstance(v, (date, datetime)) else v) for k, v in d.items()}


# --- find cover / reassign ---------------------------------------------------------------


def _knows_client(db: Session, cg_id: int, elder_id: int) -> bool:
    if (
        db.query(Assignment.id)
        .filter(Assignment.caregiver_id == cg_id, Assignment.elder_id == elder_id, Assignment.status == "ACTIVE")
        .first()
    ):
        return True
    return bool(
        db.query(CareJob.id)
        .filter(CareJob.caregiver_id == cg_id, CareJob.elder_id == elder_id, CareJob.status == "completed")
        .first()
    )


def _visits_that_day(db: Session, cg_id: int, at: datetime) -> int:
    day = _aware(at).astimezone(IST).date()
    start = datetime.combine(day, time(0, 0), tzinfo=IST).astimezone(timezone.utc)
    return (
        db.query(CareJob.id)
        .filter(
            CareJob.caregiver_id == cg_id,
            CareJob.status.in_(OPEN_STATUSES),
            CareJob.scheduled_at >= start,
            CareJob.scheduled_at < start + timedelta(days=1),
        )
        .count()
    )


def cover_suggestions(db: Session, user: User, job_id: int, *, limit: int = 8) -> dict:
    """Caregivers free for this visit: no clash and not on leave. Same team first,
    then those who know the client, then the lightest day."""
    job = db.get(CareJob, job_id)
    if not job:
        raise_not_found("Job not found")
    elder = care_jobs._elder_for(db, user, job.elder_id)
    if not job.scheduled_at:
        raise_bad_request("This visit has no time yet")
    current = db.get(Caregiver, job.caregiver_id) if job.caregiver_id else None
    team_manager = (current.manager_user_id if current else None) or elder.manager_user_id
    q = db.query(Caregiver).filter(Caregiver.tenant_id == elder.tenant_id)
    team = team_caregiver_ids(db, user)
    if team is not None:
        q = q.filter(Caregiver.id.in_(team or {-1}))
    out, busy = [], 0
    for cg in q.all():
        if current and cg.id == current.id:
            continue
        if (cg.status or "ACTIVE").upper() in INACTIVE_CAREGIVER:
            continue
        if clash_reason(db, cg, job.scheduled_at, job.duration_minutes, skip_ids={job.id}):
            busy += 1
            continue
        out.append(
            {
                "caregiver_id": cg.id,
                "name": _name(cg.first_name, cg.last_name),
                "phone": cg.phone or "",
                "same_team": bool(team_manager and cg.manager_user_id == team_manager),
                "knows_client": _knows_client(db, cg.id, elder.id),
                "visits_that_day": _visits_that_day(db, cg.id, job.scheduled_at),
            }
        )
    out.sort(key=lambda r: (not r["same_team"], not r["knows_client"], r["visits_that_day"], r["name"]))
    return {"job": care_jobs.serialize(db, job), "suggestions": out[:limit], "busy_count": busy}


def bulk_reassign(db: Session, user: User, job_ids: list[int], caregiver_id: int | None, *, force: bool = False) -> dict:
    """Give several visits to one caregiver (or unassign). Clashes are reported, not
    skipped silently; force=true books anyway. Each family hears once."""
    if not job_ids:
        raise_bad_request("Pick at least one visit")
    moved, failed = [], []
    told: dict[int, list[str]] = defaultdict(list)
    names: dict[int, tuple[str, str]] = {}
    for jid in dict.fromkeys(int(j) for j in job_ids):
        job = db.get(CareJob, jid)
        if not job:
            failed.append({"job_id": jid, "reason": "Visit not found"})
            continue
        try:
            elder = care_jobs._elder_for(db, user, job.elder_id)
        except Exception:
            failed.append({"job_id": jid, "reason": "Visit not found"})
            continue
        if job.status not in MOVABLE:
            failed.append({"job_id": jid, "reason": "This visit has already started or closed"})
            continue
        cg = care_jobs._caregiver_for(db, user, elder, caregiver_id)
        if cg and job.caregiver_id == cg.id:
            continue
        if cg and job.scheduled_at and not force:
            reason = clash_reason(db, cg, job.scheduled_at, job.duration_minutes, skip_ids={job.id})
            if reason:
                failed.append({"job_id": jid, "reason": reason})
                continue
        old = db.get(Caregiver, job.caregiver_id) if job.caregiver_id else None
        job.caregiver_id = cg.id if cg else None
        if cg and (job.staff_note or "").startswith("Needs a caregiver:"):
            job.staff_note = ""
        db.flush()
        moved.append(job.id)
        if job.status == "scheduled" and job.scheduled_at:
            told[elder.id].append(care_jobs._family_when(job.scheduled_at))
            names[elder.id] = (old.first_name if old else "", cg.first_name if cg else "")
    for elder_id, whens in told.items():
        elder = db.get(Elder, elder_id)
        old_name, new_name = names[elder_id]
        if new_name:
            instead = f" instead of {old_name}" if old_name else ""
            body = f"{new_name} will visit{instead} on {', '.join(whens)}."
        else:
            body = f"We are arranging a caregiver for the visit on {', '.join(whens)} and will confirm soon."
        care_jobs._notify_family(db, elder, "Change of caregiver", body)
    db.commit()
    jobs = [care_jobs.serialize(db, db.get(CareJob, j)) for j in moved]
    return {"moved": jobs, "failed": failed}

