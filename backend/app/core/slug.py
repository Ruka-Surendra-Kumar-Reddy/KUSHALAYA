"""URL-safe slugs for public tenant registration links."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models.tenant import Tenant

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    raw = _SLUG_RE.sub("-", (value or "").lower()).strip("-")
    return raw[:80] if raw else "agency"


def ensure_tenant_register_slug(
    db: Session,
    tenant: Tenant,
    *,
    commit: bool = False,
) -> str:
    """Assign a unique register_slug to a tenant if missing."""
    if tenant.register_slug:
        return tenant.register_slug

    base = slugify(tenant.name)
    candidate = base
    suffix = 0
    while (
        db.query(Tenant)
        .filter(Tenant.register_slug == candidate, Tenant.id != tenant.id)
        .first()
    ):
        suffix += 1
        candidate = f"{base}-{suffix}"

    tenant.register_slug = candidate
    if commit:
        db.commit()
        db.refresh(tenant)
    return candidate
