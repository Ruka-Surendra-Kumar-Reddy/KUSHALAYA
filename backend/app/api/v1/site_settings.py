"""Settings → Website (FIX 107/108), the lead funnel, and a family's referral link."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rbac import READ_ROLES, SYSTEM_ADMIN, TENANT_ADMIN, require_elder_portal, require_roles
from app.core.responses import raise_bad_request, raise_not_found
from app.models.user import User

router = APIRouter(prefix="/site-settings", tags=["Website settings"])
funnel_router = APIRouter(prefix="/prospects", tags=["Pipeline / Prospects"])
family_router = APIRouter(prefix="/home-safety/family", tags=["Safe Home — Family App"])


def _tenant(db: Session, user: User):
    from app.models.tenant import Tenant

    tenant = db.get(Tenant, user.tenant_id) if user.tenant_id else None
    if not tenant:
        raise_not_found("Agency not found")
    return tenant


@router.get("")
def get_site_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.livewell.site_settings import get_settings, price_label

    s = get_settings(_tenant(db, current_user))
    return {**s, "assessment_price_label": price_label(s["assessment_price_paise"])}


@router.put("")
def put_site_settings(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN, TENANT_ADMIN)),
):
    from app.livewell.site_settings import price_label, save_settings

    try:
        s = save_settings(db, _tenant(db, current_user), body)
    except ValueError as exc:
        raise_bad_request(str(exc))
    return {**s, "assessment_price_label": price_label(s["assessment_price_paise"])}


@funnel_router.get("/funnel")
def lead_funnel(
    months: int = Query(6, ge=1, le=24),
    include_closed: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.livewell.site_settings import funnel

    return funnel(db, current_user, months=months, include_closed=include_closed)


@family_router.get("/referral")
def family_referral(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """The family's own referral link: www.<site>/r/<code>."""
    from app.livewell.site_settings import referral_code
    from app.services.elder_portal_service import ElderPortalService

    elder = ElderPortalService.get_linked_elder(db, current_user)
    code = referral_code(elder.id)
    if not code:  # no SECRET_KEY configured: referral links are switched off
        return {"code": None, "link": None}
    base = (getattr(settings, "PUBLIC_SITE_URL", "") or "https://www.kushalaya.com").rstrip("/")
    return {"code": code, "link": f"{base}/r/{code}"}
