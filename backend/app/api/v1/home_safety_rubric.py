from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import ADMIN_ROLES, READ_ROLES, require_roles
from app.livewell.rubric_service import HomeSafetyRubricService, normalize_rubric
from app.livewell.stored_config import read_stored_config
from app.models.user import User
from app.schemas.home_safety_master_data import RubricPayload

router = APIRouter(prefix="/home-safety/rubric", tags=["Safe Home — Rubric"])


@router.get("", response_model=RubricPayload)
def get_home_safety_rubric(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return HomeSafetyRubricService.get_rubric(db, current_user)


@router.put("", response_model=RubricPayload)
def save_home_safety_rubric(
    data: RubricPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    return HomeSafetyRubricService.save_rubric(db, current_user, data.model_dump())
