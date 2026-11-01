from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.responses import raise_bad_request
from app.core.rbac import require_roles, SYSTEM_ADMIN, TENANT_ADMIN
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterTenantRequest,
    TokenResponse,
    UserResponse,
)
from app.schemas.elder_portal import RegisterElderPortalRequest
from pydantic import BaseModel, Field

from app.services.auth_service import (
    AuthService,
    issue_access_token,
    issue_refresh_token,
    request_password_reset,
    reset_password_with_token,
)
from app.services.elder_portal_service import ElderPortalService
from app.services.session_activity_service import SessionActivityService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register-tenant")
def register_tenant(
    data: RegisterTenantRequest,
    db: Session = Depends(get_db),
):
    return AuthService.register_tenant(db, data)


@router.post("/register-open", response_model=UserResponse)
def register_open(data: RegisterRequest, db: Session = Depends(get_db)):
    if settings.ENVIRONMENT.lower() in ("production", "prod"):
        raise_bad_request(
            "Open registration is disabled in production. "
            "Use register-tenant or an admin invite."
        )
    return AuthService.register(db, data, actor=None)


@router.post("/register", response_model=UserResponse)
def register_invite(
    data: RegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN, TENANT_ADMIN)),
):
    return AuthService.register(db, data, current_user)


def register_elder_portal(
    data: RegisterElderPortalRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user = ElderPortalService.register_portal_user(db, data)
    return AuthService._token_response(user, db=db, request=request)


# Public family self-sign-up matches on the client's phone number, so anyone who knew it could
# claim the family login. The route only exists when deliberately switched on.
if settings.ALLOW_FAMILY_SELF_REGISTER:
    router.post("/register-elder-portal", response_model=TokenResponse)(register_elder_portal)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, db: Session = Depends(get_db)):
    return AuthService.login(db, data, request=request)


@router.post("/refresh")
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    return AuthService.refresh(db, data)


@router.post("/logout")
def logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session_id = (request.headers.get("X-Session-ID") or "").strip()
    if session_id:
        SessionActivityService.end_session(db, session_id, user_id=current_user.id)
    return {"ok": True}


@router.get("/me")
def me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return AuthService.me(db, current_user)


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change your own password. Requires the current one — so a walked-away
    session can't be used to lock the real owner out of their account."""
    if not verify_password(body.current_password, current_user.password_hash):
        raise_bad_request("Your current password is incorrect")
    if body.current_password == body.new_password:
        raise_bad_request("Choose a password different from your current one")

    current_user.password_hash = hash_password(body.new_password)
    db.commit()

    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Changed password",
        summary="Password updated from the account menu",
        entity_type="user",
        entity_id=str(current_user.id),
        commit=True,
    )
    # Tokens carry a password fingerprint, so older sessions stop working; hand this
    # one fresh tokens so the person who changed it stays signed in.
    return {
        "ok": True,
        "access_token": issue_access_token(current_user),
        "refresh_token": issue_refresh_token(current_user),
    }


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=2000)
    password: str = Field(min_length=8, max_length=200)


def _session_factory() -> Session:
    from app.core.database import SessionLocal

    return SessionLocal()


def _send_reset_in_background(email: str) -> None:
    import logging

    db = _session_factory()
    try:
        request_password_reset(db, email)
    except Exception:
        logging.getLogger(__name__).exception("forgot_password_failed")
    finally:
        db.close()


@router.post("/forgot-password")
def forgot_password(
    body: ForgotPasswordRequest,
    background: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    """Always answers the same way and at the same speed, whether or not the address
    has an account: the lookup, token and email happen after the response.
    Limited to 5 requests per hour per email (429 after that, for any address)."""
    from app.services.login_throttle import check_and_record_reset_request

    check_and_record_reset_request(db, body.email, request)
    background.add_task(_send_reset_in_background, body.email)
    return {"ok": True, "message": "If that email has an account, a reset link is on its way."}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    reset_password_with_token(db, body.token, body.password)
    return {"ok": True}
