"""Deploy-scoped vertical and database resolution."""

from __future__ import annotations

from workforceos_core.database_packs import default_sqlite_url

from app.core.config import settings
from app.core.verticals import has_feature, normalize_vertical


def deploy_vertical() -> str:
    return normalize_vertical(settings.DEPLOY_VERTICAL)


def resolved_database_url() -> str:
    explicit = (settings.DATABASE_URL or "").strip()
    if explicit:
        return explicit
    return default_sqlite_url(deploy_vertical())


def deploy_has_feature(feature: str) -> bool:
    return has_feature(deploy_vertical(), feature)
