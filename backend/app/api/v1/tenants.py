from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import CARE_MANAGER, READ_ROLES, SYSTEM_ADMIN, TENANT_ADMIN, require_roles
from app.models.user import User
from app.schemas.custom_fields import (
    TenantFieldSchemasResponse,
    TenantFieldSchemasUpdate,
)
from app.schemas.elder_portal import TenantRegisterOption
from app.schemas.tenant import (
    MarketInfo,
    TenantBrandingResponse,
    TenantBrandingUpdate,
    TenantCreate,
    TenantDeleteRequest,
    TenantDeleteResponse,
    TenantResponse,
    TenantUpdate,
    ThemeInfo,
    VerticalInfo,
)
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/tenants", tags=["Tenant Management"])


@router.get("/register-options", response_model=list[TenantRegisterOption])
def list_register_tenants(db: Session = Depends(get_db)):
    from app.services.elder_portal_service import ElderPortalService

    tenants = ElderPortalService.list_register_tenants(db)
    return [{"id": t.id, "name": t.name} for t in tenants]


@router.get("/themes", response_model=list[ThemeInfo])
def list_themes():
    return TenantService.list_themes()


@router.get("/verticals", response_model=list[VerticalInfo])
def list_verticals():
    return TenantService.list_verticals()


@router.get("/markets", response_model=list[MarketInfo])
def list_markets():
    return TenantService.list_markets()


@router.get("/me/branding", response_model=TenantBrandingResponse)
def get_my_branding(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return TenantService.get_branding_for_user(db, current_user)


@router.get("/me/field-schemas", response_model=TenantFieldSchemasResponse)
def get_my_field_schemas(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return TenantService.get_field_schemas_for_user(db, current_user)


@router.patch("/me/field-schemas", response_model=TenantFieldSchemasResponse)
def update_my_field_schemas(
    data: TenantFieldSchemasUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN, TENANT_ADMIN)),
):
    if current_user.tenant_id is None:
        from app.core.responses import raise_bad_request
        raise_bad_request("No tenant assigned to user")
    tenant = TenantService.get_tenant(db, current_user.tenant_id, current_user)
    tenant = TenantService.update_field_schemas(db, tenant, data)
    return TenantService.field_schemas_dict(tenant)


@router.patch("/me/branding", response_model=TenantBrandingResponse)
def update_my_branding(
    data: TenantBrandingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN, TENANT_ADMIN, CARE_MANAGER)),
):
    if current_user.tenant_id is None:
        from app.core.responses import raise_bad_request
        raise_bad_request("No tenant assigned to user")
    tenant = TenantService.update_branding(
        db, current_user.tenant_id, data, current_user
    )
    return TenantService.branding_dict(tenant)


@router.get("", response_model=list[TenantResponse])
def get_tenants(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return TenantService.list_tenants(db, current_user)


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return TenantService.get_tenant(db, tenant_id, current_user)


@router.get("/{tenant_id}/branding", response_model=TenantBrandingResponse)
def get_tenant_branding(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN, TENANT_ADMIN)),
):
    tenant = TenantService.get_tenant(db, tenant_id, current_user)
    return TenantService.branding_dict(tenant)


@router.patch("/{tenant_id}/branding", response_model=TenantBrandingResponse)
def update_tenant_branding(
    tenant_id: int,
    data: TenantBrandingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN, TENANT_ADMIN)),
):
    tenant = TenantService.update_branding(db, tenant_id, data, current_user)
    return TenantService.branding_dict(tenant)


@router.get("/{tenant_id}/field-schemas", response_model=TenantFieldSchemasResponse)
def get_tenant_field_schemas(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN, TENANT_ADMIN)),
):
    tenant = TenantService.get_tenant(db, tenant_id, current_user)
    return TenantService.field_schemas_dict(tenant)


@router.patch("/{tenant_id}/field-schemas", response_model=TenantFieldSchemasResponse)
def update_tenant_field_schemas(
    tenant_id: int,
    data: TenantFieldSchemasUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN, TENANT_ADMIN)),
):
    tenant = TenantService.get_tenant(db, tenant_id, current_user)
    tenant = TenantService.update_field_schemas(db, tenant, data)
    return TenantService.field_schemas_dict(tenant)


@router.post("", response_model=TenantResponse)
def create_tenant(
    tenant: TenantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN)),
):
    return TenantService.create_tenant(db, tenant, current_user)


@router.patch("/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    tenant_id: int,
    data: TenantUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN)),
):
    return TenantService.update_tenant(db, tenant_id, data, current_user)


@router.delete("/{tenant_id}", response_model=TenantDeleteResponse)
def delete_tenant(
    tenant_id: int,
    body: TenantDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN)),
):
    """Hard-delete a tenant (super admin only). Global catalog products/photos are kept."""
    if current_user.role != SYSTEM_ADMIN:
        from app.core.responses import raise_bad_request

        raise_bad_request("Only system admins can delete tenants")

    from app.services.tenant_purge_service import TenantPurgeService

    return TenantPurgeService.delete_tenant(
        db,
        tenant_id,
        body.confirm_name,
        allow_protected=False,
    )
