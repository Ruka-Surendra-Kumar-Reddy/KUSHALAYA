from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import READ_ROLES, WRITE_ROLES, require_roles
from app.livewell.visit_service import HomeSafetyVisitService
from app.models.user import User
from app.schemas.home_safety_visit import (
    CareBaselinePayload,
    CareBaselineResponse,
    SafeHomeVisitCreate,
    SafeHomeVisitResponse,
    VisitPhotoAttachRequest,
    VisitStaffFeedbackRequest,
)

router = APIRouter(prefix="/home-safety/visits", tags=["Safe Home — Visits"])


@router.get("", response_model=list[SafeHomeVisitResponse])
def list_safe_home_visits(
    elder_id: int,
    days: int = 90,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.core.team_scope import assert_elder_in_team

    assert_elder_in_team(db, current_user, elder_id)
    return HomeSafetyVisitService.list_for_elder(
        db, current_user, elder_id, days=days
    )


@router.post("", response_model=SafeHomeVisitResponse)
def create_safe_home_visit(
    data: SafeHomeVisitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    payload = data.model_dump()
    elder_id = payload.pop("elder_id")
    return HomeSafetyVisitService.create_for_elder(db, current_user, elder_id, payload)


@router.post("/{elder_id}/{visit_id}/staff-feedback", response_model=SafeHomeVisitResponse)
def add_visit_staff_feedback(
    elder_id: int,
    visit_id: str,
    data: VisitStaffFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return HomeSafetyVisitService.add_staff_feedback(
        db, current_user, elder_id, visit_id, rating=data.rating, comment=data.comment
    )


@router.post("/{elder_id}/{visit_id}/photos", response_model=SafeHomeVisitResponse)
def attach_visit_photos(
    elder_id: int,
    visit_id: str,
    data: VisitPhotoAttachRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return HomeSafetyVisitService.attach_photos(
        db, current_user, elder_id, visit_id, data.photo_ids
    )


@router.get("/baseline/{elder_id}", response_model=CareBaselineResponse)
def get_care_baseline(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return HomeSafetyVisitService.get_baseline_for_elder(db, current_user, elder_id)


@router.put("/baseline/{elder_id}", response_model=CareBaselineResponse)
def put_care_baseline(
    elder_id: int,
    data: CareBaselinePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return HomeSafetyVisitService.put_baseline_for_elder(
        db, current_user, elder_id, data.model_dump()
    )
