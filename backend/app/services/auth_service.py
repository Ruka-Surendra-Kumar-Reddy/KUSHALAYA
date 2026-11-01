from fastapi import Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.rbac import CARE_MANAGER, CAREGIVER, SYSTEM_ADMIN, TENANT_ADMIN, VIEWER
from app.models.caregiver import Caregiver
from app.core.responses import raise_bad_request, raise_conflict
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.markets import normalize_market
from app.core.slug import ensure_tenant_register_slug
from app.core.deploy import deploy_vertical
from app.core.verticals import normalize_vertical
from app.models.tenant import Tenant
from app.livewell.family_contacts import clean_phone
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterTenantRequest,
)
from app.services.audit_service import AuditService
from app.services.session_activity_service import SessionActivityService


ALLOWED_REGISTER_ROLES = {CARE_MANAGER, VIEWER}


def _bind_to_user(token: str, user: User, extra: dict | None = None) -> str:
    """Add `uid` and `pwv` claims to a token minted by workforceos-core."""
    from jose import jwt

    from app.core.auth import password_fingerprint
    from app.core.security import ALGORITHM, SECRET_KEY

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    payload["uid"] = user.id
    payload["pwv"] = password_fingerprint(user)
    payload.update(extra or {})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def issue_access_token(user: User) -> str:
    return _bind_to_user(
        create_access_token(
            user.email,
            role=user.role,
            tenant_id=user.tenant_id,
            elder_id=user.elder_id,
            caregiver_id=user.caregiver_id,
        ),
        user,
    )


def issue_refresh_token(user: User, auth_time: float | None = None) -> str:
    """Refresh token with the sign-in time (`auth_time`) and when it was minted (`lst`),
    kept for session tracking; there is no idle or absolute limit (session_policy)."""
    import time

    now = int(time.time())
    return _bind_to_user(
        create_refresh_token(user.email),
        user,
        {"auth_time": int(auth_time) if auth_time else now, "lst": now},
    )


class AuthService:

    @staticmethod
    def _token_response(user: User, db: Session | None = None, request: Request | None = None) -> dict:
        result = {
            "access_token": issue_access_token(user),
            "refresh_token": issue_refresh_token(user),
            "token_type": "bearer",
            "email": user.email,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "elder_id": user.elder_id,
            "caregiver_id": user.caregiver_id,
            "session_id": None,
        }
        if db is not None:
            from app.core.session_policy import policy_for

            result["idle_minutes"] = policy_for(db, user)["idle_minutes"]
            try:
                session = SessionActivityService.start_session(db, user, request=request)
                db.commit()
                result["session_id"] = session.id
            except Exception:
                db.rollback()
                # Auth must not fail if session tracking is unavailable
                import logging

                logging.getLogger(__name__).exception("session_start_failed user=%s", user.id)
        return result

    @staticmethod
    def register_tenant(db: Session, data: RegisterTenantRequest) -> dict:
        if db.query(User).filter(User.email == data.email).first():
            raise_conflict("Email already registered")
        if db.query(Tenant).filter(Tenant.name == data.tenant_name).first():
            raise_conflict("Tenant name already exists")

        vertical = normalize_vertical(data.vertical or deploy_vertical())
        deployed = deploy_vertical()
        if vertical != deployed:
            raise_bad_request(
                f"This deployment only supports {deployed} tenants"
            )
        market = normalize_market(data.market, country=data.country)
        country = data.country or (
            "United States" if market == "US" else "India"
        )

        tenant = Tenant(
            name=data.tenant_name,
            email=data.tenant_email,
            phone=data.phone,
            address=data.address,
            city=data.city,
            state=data.state,
            country=country,
            market=market,
            vertical=vertical,
            portal_title=data.tenant_name,
        )
        db.add(tenant)
        db.flush()
        ensure_tenant_register_slug(db, tenant)

        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            role=TENANT_ADMIN,
            tenant_id=tenant.id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        result = AuthService._token_response(user, db=db)
        result["user"] = {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "elder_id": user.elder_id,
            "caregiver_id": user.caregiver_id,
        }
        return result

    @staticmethod
    def register(db: Session, data: RegisterRequest, actor: User | None) -> dict:
        if db.query(User).filter(User.email == data.email).first():
            raise_conflict("Email already registered")

        if actor:
            if actor.role not in {SYSTEM_ADMIN, TENANT_ADMIN}:
                raise_bad_request("Only admins can invite users")
            if actor.role == TENANT_ADMIN and actor.tenant_id != data.tenant_id:
                raise_bad_request("Cannot invite users to another tenant")
        elif data.role not in ALLOWED_REGISTER_ROLES:
            raise_bad_request("Invalid role for self-registration")

        if data.role == SYSTEM_ADMIN:
            raise_bad_request("Cannot register system admin via API")
        if data.role == CAREGIVER and data.caregiver_id is None:
            raise_bad_request("caregiver_id is required for CAREGIVER role")
        if data.role == CAREGIVER and actor is None:
            raise_bad_request("Caregiver accounts must be created by an admin")

        tenant = db.query(Tenant).filter(Tenant.id == data.tenant_id).first()
        if not tenant:
            raise_bad_request("Tenant not found")

        caregiver_id = None
        if data.role == CAREGIVER:
            cg = (
                db.query(Caregiver)
                .filter(
                    Caregiver.id == data.caregiver_id,
                    Caregiver.tenant_id == data.tenant_id,
                )
                .first()
            )
            if not cg:
                raise_bad_request("Caregiver not found for this tenant")
            existing = (
                db.query(User)
                .filter(User.caregiver_id == cg.id, User.role == CAREGIVER)
                .first()
            )
            if existing:
                raise_conflict("Caregiver portal account already exists")
            caregiver_id = cg.id
            first_name = data.first_name or cg.first_name
            last_name = data.last_name or cg.last_name
        else:
            first_name = data.first_name
            last_name = data.last_name

        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            first_name=first_name,
            last_name=last_name,
            role=data.role,
            tenant_id=data.tenant_id,
            caregiver_id=caregiver_id,
            phone=clean_phone(data.phone) or None,
        )
        db.add(user)
        db.flush()
        AuditService.log(
            db,
            tenant_id=data.tenant_id,
            user_id=actor.id if actor else None,
            entity_type="user",
            entity_id=int(user.id),
            action="user_invited" if actor else "user_self_registered",
            old_value=None,
            new_value={
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
                "tenant_id": user.tenant_id,
                "caregiver_id": user.caregiver_id,
                "status": user.status,
            },
        )
        db.commit()
        db.refresh(user)

        return {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "elder_id": user.elder_id,
            "caregiver_id": user.caregiver_id,
        }

    @staticmethod
    def login(db: Session, data: LoginRequest, request: Request | None = None) -> dict:
        # Case-insensitive and whitespace-tolerant: "Manager@Example.com " must
        # sign in the same account as "manager@example.com".
        from app.services import login_throttle

        ident = data.email.strip().lower()
        # Brute-force guard (429) — runs before any lookup so unknown and known
        # emails behave identically.
        login_throttle.check_login_allowed(db, ident, request)
        user = db.query(User).filter(func.lower(User.email) == ident).first() if ident else None
        if not user or not verify_password(data.password, user.password_hash):
            login_throttle.record_login_failure(db, ident, request)
            raise_bad_request("Invalid credentials")
        login_throttle.record_login_success(db, ident)
        if user.status != "ACTIVE":
            raise_bad_request("Account is not active")
        return AuthService._token_response(user, db=db, request=request)

    @staticmethod
    def refresh(db: Session, data: RefreshRequest) -> dict:
        payload = decode_token(data.refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise_bad_request("Invalid refresh token")

        user = db.query(User).filter(User.email == payload.get("sub")).first()
        if not user:
            raise_bad_request("User not found")
        if user.status != "ACTIVE":
            raise_bad_request("Account is not active")
        from app.core.auth import token_matches_user

        if not token_matches_user(payload, user):
            raise_bad_request("Invalid refresh token")
        from app.core.security import ACCESS_TOKEN_MINUTES
        from app.core.session_policy import policy_for, refresh_rejection

        policy = policy_for(db, user)
        why = refresh_rejection(payload, policy, ACCESS_TOKEN_MINUTES)
        if why:
            raise_bad_request(why)

        return {
            "access_token": issue_access_token(user),
            # Sliding refresh token: same sign-in time, fresh "last used".
            "refresh_token": issue_refresh_token(user, auth_time=payload.get("auth_time")),
            "idle_minutes": policy["idle_minutes"],
            "token_type": "bearer",
            "email": user.email,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "elder_id": user.elder_id,
            "caregiver_id": user.caregiver_id,
            # Client keeps existing session_id across refresh
            "session_id": None,
        }

    @staticmethod
    def me(db: Session, user: User) -> dict:
        from app.core.rbac import CAREGIVER, ELDER_PORTAL
        from app.services.tenant_service import TenantService

        result = {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "tenant_id": user.tenant_id,
            "elder_id": user.elder_id,
            "caregiver_id": user.caregiver_id,
        }
        result["tenant"] = TenantService.get_branding_for_user(db, user)
        if user.role == ELDER_PORTAL:
            from app.services.elder_portal_service import ElderPortalService
            result["elder_portal"] = ElderPortalService.portal_me(db, user)
        if user.role == CAREGIVER:
            from app.services.caregiver_portal_service import CaregiverPortalService
            result["caregiver_portal"] = CaregiverPortalService.portal_me(db, user)
        return result


# --- Forgot / reset password ------------------------------------------------
# A reset link carries a signed JWT (SECRET_KEY, 1 h). It embeds a fingerprint of
# the current password hash, so it stops working once the password changes —
# i.e. each link is single use.

RESET_TOKEN_MINUTES = 60
RESET_RESEND_SECONDS = 60
_last_reset_sent: dict[int, float] = {}


def _password_fingerprint(user: User) -> str:
    from app.core.auth import password_fingerprint

    return password_fingerprint(user)


def create_password_reset_token(user: User) -> str:
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    from app.core.security import ALGORITHM, SECRET_KEY

    payload = {
        "sub": str(user.id),
        "type": "pwreset",
        "fp": _password_fingerprint(user),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def request_password_reset(db: Session, email: str) -> None:
    """Email a reset link if the address belongs to an active user. Silent otherwise."""
    import logging
    import time

    from app.core.rbac import ELDER_PORTAL
    from app.livewell import email_notifications

    ident = (email or "").strip().lower()
    if not ident:
        return
    user = db.query(User).filter(func.lower(User.email) == ident).first()
    if not user or user.status != "ACTIVE":
        return
    now = time.monotonic()
    last = _last_reset_sent.get(user.id)
    if last is not None and now - last < RESET_RESEND_SECONDS:
        return
    _last_reset_sent[user.id] = now
    family = user.role == ELDER_PORTAL
    base = email_notifications.FAMILY_URL if family else email_notifications.OPS_URL
    link = f"{base}/reset-password?token={create_password_reset_token(user)}"
    body = (
        f"Hello {user.first_name or ''},\n\n"
        "We received a request to reset your KushAlaya password. "
        f"Open this link within {RESET_TOKEN_MINUTES} minutes to choose a new one:\n\n{link}\n\n"
        "If you didn't ask for this, you can ignore this email — your password stays the same."
    )
    try:
        email_notifications.send([user.email], "Reset your password", body, family=family)
    except Exception:
        logging.getLogger(__name__).exception("password_reset_email_failed user=%s", user.id)


def reset_password_with_token(db: Session, token: str, password: str) -> None:
    from jose import JWTError, jwt

    from app.core.security import ALGORITHM, SECRET_KEY

    bad = "This reset link is invalid or has expired. Ask for a new one."
    try:
        payload = jwt.decode(token or "", SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise_bad_request(bad)
    if payload.get("type") != "pwreset":
        raise_bad_request(bad)
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise_bad_request(bad)
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.status != "ACTIVE" or payload.get("fp") != _password_fingerprint(user):
        raise_bad_request(bad)
    user.password_hash = hash_password(password)
    AuditService.log(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        entity_type="user",
        entity_id=int(user.id),
        action="password_reset_via_email",
        old_value=None,
        new_value={"email": user.email},
    )
    db.commit()
    _last_reset_sent.pop(user.id, None)
