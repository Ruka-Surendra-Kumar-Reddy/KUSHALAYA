from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import READ_ROLES, WRITE_ROLES, require_roles
from app.livewell.assessment_service import HomeSafetyAssessmentService
from app.models.user import User
from app.schemas.home_safety_assessment import (
    HomeSafetyAssessmentPayload,
    HomeSafetyAssessmentResponse,
    HomeSafetyAssessmentSummary,
)
from app.services.session_activity_service import (
    SessionActivityService,
    activity_intent_from_request,
    is_verbose_activity_log,
)

router = APIRouter(prefix="/home-safety/assessments", tags=["Safe Home — Assessments"])


@router.get("", response_model=list[HomeSafetyAssessmentSummary])
def list_assessments(
    full: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.core.team_scope import team_elder_ids

    rows = HomeSafetyAssessmentService.list_assessments(db, current_user, full=full)
    team = team_elder_ids(db, current_user)
    if team is None:
        return rows

    # Drafts not yet linked to a client stay visible to the manager who started them.
    def elder_of(r):
        return r.get("elder_id") if isinstance(r, dict) else getattr(r, "elder_id", None)

    return [r for r in rows if elder_of(r) is None or elder_of(r) in team]


@router.get("/{assessment_id}", response_model=HomeSafetyAssessmentResponse)
def get_assessment(
    assessment_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    result = HomeSafetyAssessmentService.get_assessment(db, current_user, assessment_id)
    # List hydration also hits this GET — only record an intentional open
    # (X-Activity-Intent: open) or when ACTIVITY_LOG_MODE=verbose.
    intent = activity_intent_from_request(request)
    if intent in {"open", "view"} or is_verbose_activity_log():
        SessionActivityService.record_user_action(
            db,
            request=request,
            user=current_user,
            action="Opened assessment",
            summary=f"Viewed assessment {assessment_id}",
            entity_type="assessment",
            entity_id=assessment_id,
            commit=True,
        )
    return result


@router.put("/{assessment_id}", response_model=HomeSafetyAssessmentResponse)
def upsert_assessment(
    assessment_id: str,
    data: HomeSafetyAssessmentPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    payload = data.model_dump()
    if payload["id"] != assessment_id:
        payload["id"] = assessment_id
    result = HomeSafetyAssessmentService.upsert_assessment(db, current_user, payload)
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Saved assessment",
        summary=f"Saved checklist / intake for assessment {assessment_id}",
        entity_type="assessment",
        entity_id=assessment_id,
        commit=True,
    )
    return result


@router.delete("/{assessment_id}")
def delete_assessment(
    assessment_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    HomeSafetyAssessmentService.delete_assessment(db, current_user, assessment_id)
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Deleted assessment",
        entity_type="assessment",
        entity_id=assessment_id,
        commit=True,
    )
    return {"status": "deleted", "assessment_id": assessment_id}
