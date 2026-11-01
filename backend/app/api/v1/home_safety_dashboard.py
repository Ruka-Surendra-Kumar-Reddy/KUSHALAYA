from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import READ_ROLES, require_roles
from app.livewell.dashboard_service import HomeSafetyDashboardService
from app.models.user import User

router = APIRouter(prefix="/home-safety/dashboard", tags=["Safe Home — Dashboard"])


@router.get("")
def home_safety_ops_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return HomeSafetyDashboardService.summary(db, current_user)


@router.get("/attention")
def home_safety_ops_attention(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """Open requests, unread messages, SOS alerts and today's visits for the user's team."""
    from app.livewell.dashboard_attention import attention

    return attention(db, current_user)


# Sidebar badges for every ops page: /api/v1/dashboard/nav-counts.
nav_router = APIRouter(prefix="/dashboard", tags=["Safe Home — Dashboard"])


@nav_router.get("/nav-counts")
def ops_nav_counts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """Counts for the menu badges (alerts, unread messages, schedule, clients), team scoped."""
    from app.livewell.dashboard_attention import nav_counts

    return nav_counts(db, current_user)
