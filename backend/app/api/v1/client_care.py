"""Phase 4B routes: client sheet, care plan, risk register (staff, team-scoped), handovers,
the family's read-only view and the caregiver's visit-day sheet."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import (
    READ_ROLES,
    WRITE_ROLES,
    require_caregiver_portal,
    require_elder_portal,
    require_roles,
)
from app.livewell import client_care as cc
from app.models.user import User

router = APIRouter(prefix="/home-safety/clients", tags=["Safe Home — Client care"])
handover_router = APIRouter(prefix="/home-safety/handovers", tags=["Safe Home — Handovers"])
family_router = APIRouter(prefix="/home-safety/family", tags=["Safe Home — Family App"])
caregiver_router = APIRouter(prefix="/caregiver-portal", tags=["Caregiver portal"])


class Medicine(BaseModel):
    name: str = Field(default="", max_length=120)
    dose: str = Field(default="", max_length=80)
    times: str = Field(default="", max_length=80)


class SheetUpdate(BaseModel):
    medicines: list[Medicine] | None = Field(default=None, max_length=40)
    conditions: str | None = Field(default=None, max_length=2000)
    allergies: str | None = Field(default=None, max_length=2000)
    mobility: str | None = Field(default=None, max_length=2000)
    risks: str | None = Field(default=None, max_length=2000)
    keys_access: str | None = Field(default=None, max_length=2000)
    language: str | None = Field(default=None, max_length=120)
    doctor_name: str | None = Field(default=None, max_length=200)
    doctor_phone: str | None = Field(default=None, max_length=40)
    hospital_name: str | None = Field(default=None, max_length=200)
    hospital_phone: str | None = Field(default=None, max_length=40)
    family_preferences: str | None = Field(default=None, max_length=2000)


class GoalIn(BaseModel):
    goal: str | None = Field(default=None, max_length=1000)
    target_date: date | None = None
    status: str | None = None
    interventions: list[str] | None = Field(default=None, max_length=20)
    progress: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = None


class ReviewIn(BaseModel):
    reviewed: bool = False
    review_date: date | None = None


class RiskIn(BaseModel):
    risk: str | None = Field(default=None, max_length=300)
    level: str | None = None
    mitigation: str | None = Field(default=None, max_length=2000)
    owner_user_id: int | None = None
    review_date: date | None = None
    status: str | None = None


class HandoverIn(BaseModel):
    kind: str = "shift"
    to_user_id: int
    elder_id: int | None = None
    note: str = Field(min_length=1, max_length=4000)


# --- client sheet ---------------------------------------------------------------------


@router.get("/{elder_id}/sheet")
def get_sheet(elder_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    # Keys/access and open risks are for admins and care managers only; viewers get the rest.
    audience = "staff" if user.role in WRITE_ROLES else "viewer"
    return cc.sheet_view(db, cc.staff_elder(db, user, elder_id), audience=audience)


@router.put("/{elder_id}/sheet")
def put_sheet(
    elder_id: int, data: SheetUpdate, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    return cc.save_sheet(db, user, cc.staff_elder(db, user, elder_id), data.model_dump(exclude_unset=True))


# --- care plan -----------------------------------------------------------------------


@router.get("/{elder_id}/care-plan")
def get_care_plan(elder_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return cc.care_plan_view(db, cc.staff_elder(db, user, elder_id))


@router.post("/{elder_id}/care-plan/goals", status_code=201)
def post_goal(
    elder_id: int, data: GoalIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    return cc.create_goal(db, user, cc.staff_elder(db, user, elder_id), data.model_dump(exclude_unset=True))


@router.put("/{elder_id}/care-plan/goals/{goal_id}")
def put_goal(
    elder_id: int,
    goal_id: int,
    data: GoalIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return cc.update_goal(db, cc.staff_elder(db, user, elder_id), goal_id, data.model_dump(exclude_unset=True))


@router.delete("/{elder_id}/care-plan/goals/{goal_id}")
def del_goal(
    elder_id: int, goal_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    return cc.delete_goal(db, cc.staff_elder(db, user, elder_id), goal_id)


@router.post("/{elder_id}/care-plan/review")
def post_review(
    elder_id: int, data: ReviewIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    """reviewed=true: reviewed today, next review = next reassessment due (or 6 months). Or set review_date."""
    return cc.set_review(db, user, cc.staff_elder(db, user, elder_id), data.model_dump(exclude_unset=True))


# --- risk register --------------------------------------------------------------------


@router.get("/{elder_id}/risks")
def get_risks(elder_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return cc.list_risks(db, cc.staff_elder(db, user, elder_id))


@router.post("/{elder_id}/risks", status_code=201)
def post_risk(
    elder_id: int, data: RiskIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    return cc.create_risk(db, user, cc.staff_elder(db, user, elder_id), data.model_dump(exclude_unset=True))


@router.put("/{elder_id}/risks/{risk_id}")
def put_risk(
    elder_id: int,
    risk_id: int,
    data: RiskIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return cc.update_risk(db, cc.staff_elder(db, user, elder_id), risk_id, data.model_dump(exclude_unset=True))


@router.get("/{elder_id}/handovers")
def get_client_handovers(
    elder_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))
):
    return cc.list_handovers(db, user, elder=cc.staff_elder(db, user, elder_id))


# --- care team (manager + regular caregivers) -------------------------------------------


class CareManagerIn(BaseModel):
    manager_user_id: int
    note: str | None = Field(default=None, max_length=4000)


class CareCaregiverIn(BaseModel):
    caregiver_id: int


class CareReplaceIn(BaseModel):
    caregiver_id: int
    move_visits: bool = False


@router.get("/{elder_id}/care-team")
def get_care_team(elder_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    from app.livewell import care_team as ct

    return ct.care_team(db, user, ct.staff_elder(db, user, elder_id))


@router.put("/{elder_id}/care-team/manager")
def put_care_manager(
    elder_id: int, data: CareManagerIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    from fastapi import HTTPException

    from app.livewell import care_team as ct

    if not ct.is_admin(user):
        raise HTTPException(status_code=403, detail="Only an admin can change the care manager")
    return ct.set_manager(db, user, ct.staff_elder(db, user, elder_id), data.manager_user_id, data.note)


@router.post("/{elder_id}/care-team/caregivers", status_code=201)
def post_care_caregiver(
    elder_id: int, data: CareCaregiverIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    from app.livewell import care_team as ct

    return ct.add_caregiver(db, user, ct.staff_elder(db, user, elder_id), data.caregiver_id)


@router.post("/{elder_id}/care-team/caregivers/{assignment_id}/replace")
def post_care_replace(
    elder_id: int,
    assignment_id: int,
    data: CareReplaceIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    from app.livewell import care_team as ct

    elder = ct.staff_elder(db, user, elder_id)
    return ct.replace_caregiver(db, user, elder, assignment_id, data.caregiver_id, move_visits=data.move_visits)


@router.delete("/{elder_id}/care-team/caregivers/{assignment_id}")
def delete_care_caregiver(
    elder_id: int, assignment_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))
):
    from app.livewell import care_team as ct

    return ct.remove_caregiver(db, user, ct.staff_elder(db, user, elder_id), assignment_id)


# --- handovers ------------------------------------------------------------------------


@handover_router.get("")
def get_handovers(
    box: str = Query(default="inbox", pattern="^(inbox|sent|all)$"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*READ_ROLES)),
):
    return cc.list_handovers(db, user, box=box)


@handover_router.get("/recipients")
def get_handover_recipients(db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    return cc.handover_recipients(db, user)


@handover_router.post("", status_code=201)
def post_handover(data: HandoverIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    return cc.create_handover(db, user, data.model_dump())


@handover_router.post("/{handover_id}/acknowledge")
def ack_handover(handover_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    return cc.acknowledge_handover(db, user, handover_id)


# --- family + caregiver ----------------------------------------------------------------


@family_router.get("/care-sheet")
def family_care_sheet(db: Session = Depends(get_db), user: User = Depends(require_elder_portal)):
    """Read-only: health details, medicines, doctor, goals. Never keys/access or the risk register."""
    return cc.family_care_view(db, user)


@caregiver_router.get("/jobs/{job_id}/client-sheet")
def caregiver_client_sheet(job_id: int, db: Session = Depends(get_db), user: User = Depends(require_caregiver_portal)):
    """The client sheet for this job's client, on the visit day only."""
    return cc.caregiver_sheet(db, user, job_id)
