"""Backward-compatible admin seed entry for SafeHomeOps.

Prefer: python -m app.seed_safehome_admin
Older scripts may still call: python -m app.seed_care_admin
"""

from app.seed_safehome_admin import (
    DEMO_PASSWORD,
    LEGACY_ADMIN_EMAIL,
    TENANT_ADMIN_EMAIL,
    TENANT_NAME,
    ensure_care_admin,
    ensure_tenant_admin,
    resolve_safehome_tenant as resolve_elder_care_tenant,
)

# Historical import name — now SafeHome Demo tenant.
SUNRISE_TENANT_NAME = TENANT_NAME

__all__ = [
    "DEMO_PASSWORD",
    "LEGACY_ADMIN_EMAIL",
    "SUNRISE_TENANT_NAME",
    "TENANT_ADMIN_EMAIL",
    "ensure_care_admin",
    "ensure_tenant_admin",
    "resolve_elder_care_tenant",
]


if __name__ == "__main__":
    ensure_tenant_admin()
