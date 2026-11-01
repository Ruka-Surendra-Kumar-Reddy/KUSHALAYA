from fastapi import Depends, HTTPException

from app.core.auth import get_current_user
from app.models.user import User
from workforceos_core.rbac import (
    ADMIN_ROLES,
    CAREGIVER,
    CARE_MANAGER,
    ELDER_PORTAL,
    PORTAL_ROLES,
    READ_ROLES,
    STAFF_ROLES,
    SYSTEM_ADMIN,
    TENANT_ADMIN,
    VIEWER,
    WRITE_ROLES,
    assert_tenant_access,
    is_staff_role,
    resolve_tenant_id,
)

__all__ = [
    "ADMIN_ROLES",
    "CAREGIVER",
    "CARE_MANAGER",
    "ELDER_PORTAL",
    "PORTAL_ROLES",
    "READ_ROLES",
    "STAFF_ROLES",
    "SYSTEM_ADMIN",
    "TENANT_ADMIN",
    "VIEWER",
    "WRITE_ROLES",
    "assert_tenant_access",
    "is_staff_role",
    "require_caregiver_portal",
    "require_elder_portal",
    "require_roles",
    "require_staff",
    "require_tenant",
    "resolve_tenant_id",
    "assert_elder_access",
]


def require_roles(*allowed: str):
    allowed_set = set(allowed)

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_set:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return checker


def require_staff(user: User = Depends(get_current_user)) -> User:
    if not is_staff_role(user.role):
        raise HTTPException(
            status_code=403,
            detail="Staff portal access only",
        )
    return user


def require_tenant(user: User = Depends(get_current_user)) -> User:
    if user.role == SYSTEM_ADMIN:
        return user
    if user.tenant_id is None:
        raise HTTPException(status_code=403, detail="User is not assigned to a tenant")
    return user


def require_caregiver_portal(user: User = Depends(get_current_user)) -> User:
    if user.role != CAREGIVER:
        raise HTTPException(status_code=403, detail="Caregiver portal access only")
    if user.caregiver_id is None:
        raise HTTPException(status_code=403, detail="No caregiver profile linked")
    if user.tenant_id is None:
        raise HTTPException(status_code=403, detail="Caregiver account is not active")
    return user


def require_elder_portal(user: User = Depends(get_current_user)) -> User:
    if user.role != ELDER_PORTAL:
        raise HTTPException(status_code=403, detail="Elder portal access only")
    if user.elder_id is None:
        raise HTTPException(status_code=403, detail="No elder profile linked")
    if user.tenant_id is None:
        raise HTTPException(status_code=403, detail="Family account is not active")
    return user


def assert_elder_access(user: User, elder_id: int, tenant_id: int) -> None:
    if user.role == ELDER_PORTAL:
        if user.elder_id != elder_id:
            raise HTTPException(status_code=403, detail="Access denied for this elder")
        return
    assert_tenant_access(user, tenant_id)
