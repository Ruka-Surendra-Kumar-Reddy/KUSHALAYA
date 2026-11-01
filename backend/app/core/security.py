"""Re-export WorkforceOS security helpers from workforceos-core."""

from app.core.config import settings
from workforceos_core.security import (
    ALGORITHM,
    SecuritySettings,
    configure_security,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

configure_security(
    SecuritySettings(
        secret_key=settings.SECRET_KEY,
        access_token_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_token_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
    )
)

SECRET_KEY = settings.SECRET_KEY
ACCESS_TOKEN_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS

__all__ = [
    "ALGORITHM",
    "SECRET_KEY",
    "ACCESS_TOKEN_MINUTES",
    "REFRESH_TOKEN_DAYS",
    "SecuritySettings",
    "configure_security",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
]
