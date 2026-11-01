"""Tenant vertical feature guards for API services."""

from sqlalchemy.orm import Session

from app.core.rbac import resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.core.verticals import has_feature
from app.models.tenant import Tenant
from app.models.user import User


def require_tenant_feature(db: Session, user: User, feature: str) -> Tenant:
    tid = resolve_tenant_id(user)
    if tid is None:
        raise_bad_request("Tenant context required")
    tenant = db.query(Tenant).filter(Tenant.id == tid).first()
    if not tenant:
        raise_not_found("Tenant not found")
    if not has_feature(tenant.vertical, feature):
        raise_bad_request("This module is not available for your industry vertical")
    return tenant


def require_any_tenant_feature(db: Session, user: User, *features: str) -> Tenant:
    tid = resolve_tenant_id(user)
    if tid is None:
        raise_bad_request("Tenant context required")
    tenant = db.query(Tenant).filter(Tenant.id == tid).first()
    if not tenant:
        raise_not_found("Tenant not found")
    if not any(has_feature(tenant.vertical, f) for f in features):
        raise_bad_request("This module is not available for your industry vertical")
    return tenant
