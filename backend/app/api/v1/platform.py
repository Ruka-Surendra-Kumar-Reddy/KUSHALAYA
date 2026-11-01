from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.platform_modules import list_platform_modules
from app.core.rbac import READ_ROLES, require_roles
from app.core.responses import raise_bad_request
from app.models.user import User
from app.services.reporting_service import ReportingService

router = APIRouter(tags=["Platform Services"])


@router.get("/platform/modules")
def platform_modules(
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """WorkforceOS module maturity — guides gradual platform conversion."""
    return {"modules": list_platform_modules()}


@router.get("/reporting/tenant-summary")
def tenant_summary(
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    tenant_id = current_user.tenant_id
    if tenant_id is None:
        raise_bad_request("No tenant context for reporting")
    return ReportingService.tenant_summary(tenant_id)
