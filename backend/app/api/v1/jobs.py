"""Scheduled jobs (visits, assessments, installs) — staff side. See app/livewell/care_jobs.py."""

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import READ_ROLES, WRITE_ROLES, require_roles
from app.livewell import care_jobs
from app.models.user import User

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class JobCreate(BaseModel):
    elder_id: int
    kind: str = "visit"
    title: str | None = None
    tasks: str | None = None
    location: str | None = None
    scheduled_at: datetime
    duration_minutes: int | None = None
    caregiver_id: int | None = None
    assignee_user_id: int | None = None  # assessments: the care manager
    request_id: str | None = None
    product_ids: list[str] | None = None
    staff_note: str | None = None
    force: bool = False  # book even if the caregiver or client is already booked then


class JobUpdate(BaseModel):
    title: str | None = None
    tasks: str | None = None
    location: str | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int | None = None
    caregiver_id: int | None = None
    assignee_user_id: int | None = None
    status: str | None = None
    staff_note: str | None = None
    force: bool = False


@router.get("")
def list_jobs(
    elder_id: int | None = None,
    start: datetime | None = Query(default=None, alias="from"),
    end: datetime | None = Query(default=None, alias="to"),
    open_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return care_jobs.list_jobs(
        db, current_user, elder_id=elder_id, start=start, end=end, include_closed=not open_only
    )


@router.get("/location-alerts")
def location_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """Open "visit logged away from home" notices for the signed-in staff user."""
    from app.livewell.visit_location import list_open

    return list_open(db, current_user)


@router.post("/location-alerts/{alert_id}/dismiss")
def dismiss_location_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.livewell.visit_location import dismiss

    return dismiss(db, current_user, alert_id)


# --- Start an assessment from the office (client or lead) — app/livewell/assessment_start.py


class AssessmentStart(BaseModel):
    elder_id: int | None = None
    lead_id: int | None = None
    new: bool = False  # true = start a new one even when a draft is open


@router.get("/assessment-board")
def assessment_board(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """The Assessments page: scheduled, in progress and completed in one list."""
    from app.livewell.assessment_start import board

    return board(db, current_user)


@router.get("/assessment-targets")
def assessment_targets(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Clients and open leads for "New assessment", each with its unfinished draft."""
    from app.livewell.assessment_start import targets

    return targets(db, current_user)


@router.get("/assessment-draft")
def assessment_draft(
    elder_id: int | None = None,
    lead_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell.assessment_start import draft_for

    return {"draft": draft_for(db, current_user, elder_id=elder_id, lead_id=lead_id)}


@router.post("/start-assessment")
def start_assessment(
    data: AssessmentStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell.assessment_start import start

    return start(db, current_user, elder_id=data.elder_id, lead_id=data.lead_id, new=data.new)


class AssessmentBook(BaseModel):
    lead_id: int
    scheduled_at: datetime
    assignee_user_id: int | None = None
    force: bool = False


@router.post("/book-assessment", status_code=201)
def book_assessment(
    data: AssessmentBook,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """A new lead asks for a visit later: book the assessment and move the lead to "Assessment booked"."""
    from app.livewell.assessment_start import book

    return book(
        db, current_user, lead_id=data.lead_id, scheduled_at=data.scheduled_at,
        assignee_user_id=data.assignee_user_id, force=data.force,
    )


@router.post("", status_code=201)
def create_job(
    data: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return care_jobs.create_job(db, current_user, data.model_dump())


@router.patch("/{job_id}")
def update_job(
    job_id: int,
    data: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return care_jobs.update_job(db, current_user, job_id, data.model_dump(exclude_unset=True))


# --- Care manager runs the visit (same steps as the caregiver app) ---------------


class StaffLocation(BaseModel):
    """Where staff did it from, when the browser gave a location (office staff may have none)."""

    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy: float | None = Field(default=None, ge=0)


class StaffJobStatus(StaffLocation):
    status: str
    note: str | None = None


class StaffReport(StaffLocation):
    checks: dict = {}
    kushlife: dict | None = None
    checklist: dict | list | None = None
    note: str = ""
    hazard: dict | None = None


class StaffAssessmentSave(BaseModel):
    ratings: dict = {}
    item_notes: dict = {}
    answer_labels: dict = {}
    resident_profile: dict = {}
    notes: str = ""
    complete: bool = False


@router.post("/{job_id}/progress")
def staff_progress(
    job_id: int,
    data: StaffJobStatus,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """On the way / Arrived, done by the care manager for the caregiver."""
    return care_jobs.caregiver_set_status(
        db, current_user, job_id, data.status,
        lat=data.latitude, lng=data.longitude, accuracy=data.accuracy, note=data.note,
    )


class StaffLivePosition(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy: float | None = Field(default=None, ge=0)


@router.post("/{job_id}/location")
def staff_live_location(
    job_id: int,
    data: StaffLivePosition,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """A care manager on the way shares their browser location from the Visits page
    (only the newest point is kept; {"tracking": false} once they have arrived)."""
    from app.livewell.live_location import record

    return record(db, current_user, job_id, lat=data.latitude, lng=data.longitude, accuracy=data.accuracy)


class PastVisit(StaffLocation):
    elder_id: int
    visited_at: datetime
    caregiver_id: int | None = None
    title: str = ""
    duration_minutes: int | None = None
    checks: dict = {}
    kushlife: dict | None = None
    checklist: dict | list | None = None
    note: str = ""
    hazard: dict | None = None


@router.post("/log-past", status_code=201)
def log_past_visit(
    data: PastVisit,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """A visit that already happened (no booking): saved as completed with its report."""
    from app.livewell.visit_reports import log_past_visit as _log

    return _log(db, current_user, data.model_dump())


@router.post("/{job_id}/report")
def staff_report(
    job_id: int,
    data: StaffReport,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell.visit_reports import complete_with_report

    return complete_with_report(db, current_user, job_id, data.model_dump())


@router.get("/{job_id}/assessment")
def staff_assessment(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell.field_assessment import load_for_job

    return load_for_job(db, current_user, job_id)


@router.put("/{job_id}/assessment")
def staff_assessment_save(
    job_id: int,
    data: StaffAssessmentSave,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell.field_assessment import save_for_job

    return save_for_job(db, current_user, job_id, data.model_dump())


@router.get("/{job_id}/suggestions")
def staff_suggestions(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell.field_assessment import suggestions_for_job

    return suggestions_for_job(db, current_user, job_id)


@router.post("/{job_id}/photos")
async def staff_photo(
    job_id: int,
    file: UploadFile = File(...),
    room_type: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell.field_assessment import add_photo

    content = await file.read()
    return add_photo(
        db,
        current_user,
        job_id,
        file_name=file.filename or "photo.jpg",
        content=content,
        content_type=file.content_type or "image/jpeg",
        room_type=room_type,
        caption=None,
    )


class AssessmentClientSave(BaseModel):
    details: dict = {}
    location: dict = {}
    beneficiaries: list = []


@router.put("/{job_id}/assessment/client")
def staff_assessment_client(
    job_id: int,
    data: AssessmentClientSave,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell.field_assessment import save_client

    return save_client(db, current_user, job_id, data.model_dump())
