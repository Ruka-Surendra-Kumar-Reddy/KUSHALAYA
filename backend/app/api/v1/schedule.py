"""Repeating visits, weekly roster, leave and cover — staff side, plus the caregiver's
own leave requests. See app/livewell/care_series.py and app/livewell/leave_cover.py."""

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import READ_ROLES, WRITE_ROLES, require_caregiver_portal, require_roles
from app.livewell import care_series, leave_cover
from app.models.user import User

router = APIRouter(prefix="/schedule", tags=["Schedule"])
caregiver_router = APIRouter(prefix="/caregiver-portal/leave", tags=["Caregiver portal"])


class SeriesCreate(BaseModel):
    elder_id: int
    caregiver_id: int | None = None
    weekdays: list[int]  # Monday = 0
    time: str  # IST "HH:MM"
    duration_minutes: int = 60
    start_date: date | None = None
    end_date: date | None = None
    weeks: int | None = None
    title: str | None = None
    tasks: str | None = None


class SeriesChange(BaseModel):
    job_id: int
    scope: str = "one"  # one | following
    time: str | None = None
    caregiver_id: int | None = None
    weekdays: list[int] | None = None
    duration_minutes: int | None = None
    title: str | None = None
    tasks: str | None = None
    force: bool = False


class SeriesEnd(BaseModel):
    end_date: date | None = None  # last day kept; empty = stop now


class LeaveCreate(BaseModel):
    leave_type: str = "ANNUAL"
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=2000)


class StaffLeaveCreate(LeaveCreate):
    caregiver_id: int
    approve: bool = False


class LeaveReject(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class Reassign(BaseModel):
    job_ids: list[int]
    caregiver_id: int | None = None
    force: bool = False


# --- repeating visits ---------------------------------------------------------------


@router.get("/series")
def list_series(
    elder_id: int | None = None,
    include_ended: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return care_series.list_series(db, current_user, elder_id=elder_id, include_ended=include_ended)


@router.post("/series", status_code=201)
def create_series(
    data: SeriesCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return care_series.create_series(db, current_user, data.model_dump())


@router.post("/series/{series_id}/change")
def change_series(
    series_id: int,
    data: SeriesChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return care_series.change_series(db, current_user, series_id, data.model_dump(exclude_unset=True))


@router.post("/series/{series_id}/end")
def end_series(
    series_id: int,
    data: SeriesEnd,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return care_series.end_series(db, current_user, series_id, data.model_dump())


@router.get("/roster")
def roster(
    week: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return care_series.weekly_roster(db, current_user, week)


# --- leave and cover ------------------------------------------------------------------


@router.get("/leave")
def list_leave(
    status: str | None = None,
    start: date | None = None,
    end: date | None = None,
    caregiver_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return leave_cover.list_leave(
        db, current_user, status=status, start=start, end=end, caregiver_id=caregiver_id
    )


@router.post("/leave", status_code=201)
def staff_leave(
    data: StaffLeaveCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return leave_cover.staff_request(db, current_user, data.model_dump())


@router.post("/leave/{leave_id}/approve")
def approve_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return leave_cover.approve(db, current_user, leave_id)


@router.post("/leave/{leave_id}/reject")
def reject_leave(
    leave_id: int,
    data: LeaveReject,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return leave_cover.reject(db, current_user, leave_id, data.reason)


@router.get("/leave/{leave_id}/affected")
def affected(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return leave_cover.affected_visits(db, current_user, leave_id)


@router.get("/cover/{job_id}")
def cover(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return leave_cover.cover_suggestions(db, current_user, job_id)


@router.post("/reassign")
def reassign(
    data: Reassign,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return leave_cover.bulk_reassign(db, current_user, data.job_ids, data.caregiver_id, force=data.force)


# --- caregiver app ----------------------------------------------------------------------


@caregiver_router.get("")
def my_leave(db: Session = Depends(get_db), current_user: User = Depends(require_caregiver_portal)):
    return leave_cover.caregiver_list(db, current_user)


@caregiver_router.post("", status_code=201)
def request_leave(
    data: LeaveCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_caregiver_portal),
):
    return leave_cover.caregiver_request(db, current_user, data.model_dump())


@caregiver_router.post("/{leave_id}/cancel")
def cancel_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_caregiver_portal),
):
    return leave_cover.caregiver_cancel(db, current_user, leave_id)
