from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import ADMIN_ROLES, READ_ROLES, require_roles
from app.livewell.solution_service import HomeSafetySolutionService
from app.models.user import User
from app.schemas.home_safety_solutions import SolutionLibrary

router = APIRouter(prefix="/home-safety/solutions", tags=["Safe Home — Solutions"])


@router.get("", response_model=SolutionLibrary)
def get_home_safety_solutions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return HomeSafetySolutionService.get_solutions(db, current_user)


@router.put("", response_model=SolutionLibrary)
def save_home_safety_solutions(
    data: SolutionLibrary,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    return HomeSafetySolutionService.save_solutions(db, current_user, data.model_dump())
