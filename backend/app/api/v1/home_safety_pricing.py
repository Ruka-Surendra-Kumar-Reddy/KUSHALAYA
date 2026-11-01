from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import ADMIN_ROLES, READ_ROLES, require_roles
from app.livewell.pricing_service import HomeSafetyPricingService
from app.models.user import User
from app.schemas.home_safety_pricing import SafeHomePricingConfig

router = APIRouter(prefix="/home-safety/pricing", tags=["Safe Home — Pricing"])


@router.get("", response_model=SafeHomePricingConfig)
def get_home_safety_pricing(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return HomeSafetyPricingService.get_pricing(db, current_user)


@router.put("", response_model=SafeHomePricingConfig)
def save_home_safety_pricing(
    data: SafeHomePricingConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    return HomeSafetyPricingService.save_pricing(db, current_user, data.model_dump())
