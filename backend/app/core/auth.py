from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from fastapi.security import HTTPBearer
from fastapi.security import HTTPAuthorizationCredentials

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token

from app.models.user import User

security = HTTPBearer()


def password_fingerprint(user: User) -> str:
    """Short, non-reversible marker of the current password hash. Tokens carry it as
    `pwv`, so changing or resetting a password retires every older token."""
    import hashlib

    return hashlib.sha256((user.password_hash or "").encode()).hexdigest()[:16]


def token_matches_user(payload: dict, user: User) -> bool:
    """`uid` / `pwv` are checked when present; older tokens without them still work."""
    uid = payload.get("uid")
    if uid is not None and str(uid) != str(user.id):
        return False
    pwv = payload.get("pwv")
    if pwv is not None and pwv != password_fingerprint(user):
        return False
    return True


#: Marketing logins read like a care manager but may only change these areas.
MARKETING_WRITE_PREFIXES = (
    "/api/v1/auth/", "/api/v1/sales/leads", "/api/v1/vendors", "/api/v1/contracts", "/api/v1/blog",
)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):

    payload = decode_token(
        credentials.credentials
    )

    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

    email = payload.get("sub")

    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    # Email reused by another account, or password changed since the token was issued.
    if not token_matches_user(payload, user):
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please sign in again."
        )

    # A deactivated account keeps its JWTs until they expire; reject them here
    # so deactivation takes effect on the next request, not the next login.
    if (user.status or "ACTIVE") != "ACTIVE":
        raise HTTPException(
            status_code=401,
            detail="Account is not active"
        )

    if (
        user.access_profile == "marketing"
        and request.method not in ("GET", "HEAD", "OPTIONS")
        and not request.url.path.startswith(MARKETING_WRITE_PREFIXES)
    ):
        raise HTTPException(status_code=403, detail="Your account can view this but not change it.")

    return user