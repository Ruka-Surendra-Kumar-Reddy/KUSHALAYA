"""Incident reports (#97) and the per-client visit checklist (#99).

Staff:     /home-safety/incident-reports…, /home-safety/clients/{id}/visit-checklist…
Caregiver: POST /caregiver-portal/jobs/{job_id}/incident (own visits only)
Family:    GET /home-safety/family/incident-reports (reviewed only, plain summary)
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import READ_ROLES, WRITE_ROLES, require_caregiver_portal, require_elder_portal, require_roles
from app.livewell import incident_reports as svc
from app.livewell import visit_checklist
from app.models.user import User

router = APIRouter(prefix="/home-safety/incident-reports", tags=["Safe Home — Incident reports"])
checklist_router = APIRouter(prefix="/home-safety/clients", tags=["Safe Home — Clients"])
caregiver_router = APIRouter(prefix="/caregiver-portal", tags=["Caregiver portal"])
family_router = APIRouter(prefix="/home-safety/family", tags=["Safe Home — Family App"])


class FollowUp(BaseModel):
    id: str | None = None
    action: str = Field(default="", max_length=300)
    owner: str = Field(default="", max_length=120)
    due_date: str | None = None
    done: bool = False


class ReportIn(BaseModel):
    kind: str
    what_happened: str = Field(max_length=4000)
    occurred_at: str | None = None
    location: str = Field(default="", max_length=300)
    injury: str = Field(default="", max_length=2000)
    action_taken: str = Field(default="", max_length=2000)
    witnesses: str = Field(default="", max_length=500)
    family_informed: bool = False
    family_informed_at: str | None = None
    serious: bool = False


class StaffReportIn(ReportIn):
    elder_id: int
    care_job_id: int | None = None
    follow_ups: list[FollowUp] = Field(default_factory=list)


class ReportPatch(BaseModel):
    kind: str | None = None
    what_happened: str | None = Field(default=None, max_length=4000)
    occurred_at: str | None = None
    location: str | None = Field(default=None, max_length=300)
    injury: str | None = Field(default=None, max_length=2000)
    action_taken: str | None = Field(default=None, max_length=2000)
    witnesses: str | None = Field(default=None, max_length=500)
    family_informed: bool | None = None
    family_informed_at: str | None = None
    serious: bool | None = None
    follow_ups: list[FollowUp] | None = None
    staff_notes: str | None = Field(default=None, max_length=4000)
    family_summary: str | None = Field(default=None, max_length=2000)


class ReviewIn(BaseModel):
    staff_notes: str | None = Field(default=None, max_length=4000)
    family_summary: str | None = Field(default=None, max_length=2000)
    follow_ups: list[FollowUp] | None = None


class CloseIn(BaseModel):
    outcome: str = Field(default="", max_length=2000)
    family_summary: str | None = Field(default=None, max_length=2000)


@router.get("")
def list_reports(
    elder_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return svc.list_reports(db, current_user, elder_id=elder_id, status=status)


@router.post("", status_code=201)
def create_report(
    data: StaffReportIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return svc.staff_create(db, current_user, data.model_dump())


@router.get("/{report_id}")
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return svc.get_report(db, current_user, report_id)


@router.put("/{report_id}")
def update_report(
    report_id: int,
    data: ReportPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    body = {k: v for k, v in data.model_dump().items() if v is not None}
    if data.family_informed is False:
        body["family_informed"] = False
    return svc.update_report(db, current_user, report_id, body)


@router.post("/{report_id}/review")
def review_report(
    report_id: int,
    data: ReviewIn | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    body = {k: v for k, v in (data.model_dump() if data else {}).items() if v is not None}
    return svc.review_report(db, current_user, report_id, body)


@router.post("/{report_id}/close")
def close_report(
    report_id: int,
    data: CloseIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return svc.close_report(db, current_user, report_id, data.model_dump())


# --- caregiver ----------------------------------------------------------------------


@caregiver_router.post("/jobs/{job_id}/incident", status_code=201)
def caregiver_file_report(
    job_id: int,
    data: ReportIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_caregiver_portal),
):
    """File an incident report on one of my visits (fall, near-miss, medicine mistake…)."""
    return svc.caregiver_create(db, user, job_id, data.model_dump())


# --- family -------------------------------------------------------------------------


@family_router.get("/incident-reports")
def family_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """Reports about my parent the care manager has reviewed, in plain words."""
    from app.services.elder_portal_service import ElderPortalService

    return svc.family_list(db, ElderPortalService.get_linked_elder(db, current_user))


# --- visit checklist (#99) ----------------------------------------------------------


class ChecklistItem(BaseModel):
    id: str | None = None
    label: str = Field(max_length=200)
    source: str | None = None


class ChecklistIn(BaseModel):
    items: list[ChecklistItem] = Field(default_factory=list, max_length=30)


def _client(db: Session, user: User, elder_id: int):
    return svc._elder_for_staff(db, user, elder_id)


@checklist_router.get("/{elder_id}/visit-checklist")
def get_visit_checklist(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    elder = _client(db, current_user, elder_id)
    return {**visit_checklist.get_checklist(elder), "suggestions": visit_checklist.rubric_suggestions(db, elder)}


@checklist_router.put("/{elder_id}/visit-checklist")
def put_visit_checklist(
    elder_id: int,
    data: ChecklistIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    elder = _client(db, current_user, elder_id)
    items = [i.model_dump() for i in data.items]
    return visit_checklist.save_checklist(db, elder, items, current_user)
