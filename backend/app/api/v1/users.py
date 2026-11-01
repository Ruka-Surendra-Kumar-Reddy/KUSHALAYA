from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import (
    CARE_MANAGER,
    ELDER_PORTAL,
    READ_ROLES,
    SYSTEM_ADMIN,
    TENANT_ADMIN,
    require_roles,
)
from app.core.responses import raise_bad_request, raise_conflict
from app.models.user import User
from app.schemas.auth import RegisterRequest, UserResponse
from app.services.auth_service import AuthService
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])

EDIT_ROLES = (SYSTEM_ADMIN, TENANT_ADMIN, CARE_MANAGER)


class UserUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    role: str | None = Field(default=None, min_length=1, max_length=50)
    # Needed when a manager with a team becomes Admin/Viewer.
    reassign_to_manager_id: int | None = None


class DeactivateBody(BaseModel):
    reassign_to_manager_id: int | None = None


class PasswordSet(BaseModel):
    password: str = Field(min_length=8, max_length=200)


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return UserService.list_users(db, current_user)


@router.post("/invite", response_model=UserResponse)
def invite_user(
    data: RegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN, TENANT_ADMIN)),
):
    data.role = (data.role or "").strip().upper()
    if data.role == ELDER_PORTAL:
        raise_bad_request("Family logins are added from the client's page, not here")
    data.email = data.email.strip().lower()
    if db.query(User).filter(func.lower(User.email) == data.email).first():
        raise_conflict("Email already registered")
    return AuthService.register(db, data, current_user)


@router.get("/{user_id}/caseload")
def manager_caseload(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN, TENANT_ADMIN)),
):
    """How many clients and caregivers a manager has (for the deactivate dialog)."""
    target = UserService._managed_user(db, current_user, user_id)
    if target.role != CARE_MANAGER:
        return {"clients": 0, "caregivers": 0}
    return UserService.caseload(db, target)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """Edit name / email, and (admins only) the role. Admins cannot change their own role,
    the last admin cannot be demoted, and managers cannot edit admins."""
    return UserService.update_profile(db, current_user, user_id, data.model_dump(exclude_unset=True))


@router.post("/{user_id}/password", response_model=UserResponse)
def set_user_password(
    user_id: int,
    data: PasswordSet,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """Set a new password for a staff member or caregiver (managers: own team's caregivers)."""
    return UserService.set_password(db, current_user, user_id, data.password)


@router.post("/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: int,
    data: DeactivateBody | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN, TENANT_ADMIN)),
):
    """Mark the account INACTIVE: login, token refresh and bearer tokens are rejected.
    A manager with a team needs `reassign_to_manager_id`; the hand-over is atomic."""
    reassign = data.reassign_to_manager_id if data else None
    return UserService.set_active(db, current_user, user_id, False, reassign)


@router.post("/{user_id}/reactivate", response_model=UserResponse)
def reactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN, TENANT_ADMIN)),
):
    return UserService.set_active(db, current_user, user_id, True)
