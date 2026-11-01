"""Global SafeHome product catalog — shared across all tenants."""

from __future__ import annotations

from copy import deepcopy

from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.livewell.config_keys import CATALOG_KEY
from app.livewell.catalog_defaults import DEFAULT_CATALOG
from app.models.app_global_setting import AppGlobalSetting
from app.models.tenant import Tenant

GLOBAL_CATALOG_KEY = CATALOG_KEY  # home_safety_catalog


def ensure_app_global_settings_table() -> None:
    """Create app_global_settings if missing (prod may not have run migrate yet)."""
    from app.core.database import engine

    AppGlobalSetting.__table__.create(bind=engine, checkfirst=True)


def _missing_global_settings_table(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "app_global_settings" in msg and (
        "does not exist" in msg
        or "no such table" in msg
        or "undefinedtable" in msg
    )


def load_raw_global_catalog(db: Session) -> dict | None:
    try:
        row = (
            db.query(AppGlobalSetting)
            .filter(AppGlobalSetting.key == GLOBAL_CATALOG_KEY)
            .first()
        )
    except (ProgrammingError, OperationalError) as exc:
        db.rollback()
        if _missing_global_settings_table(exc):
            return None
        raise
    if row and isinstance(row.value, dict):
        return deepcopy(row.value)
    return None


def save_raw_global_catalog(db: Session, catalog: dict, *, commit: bool = True) -> None:
    payload = deepcopy(catalog)
    for attempt in (1, 2):
        try:
            row = (
                db.query(AppGlobalSetting)
                .filter(AppGlobalSetting.key == GLOBAL_CATALOG_KEY)
                .first()
            )
            if row is None:
                db.add(AppGlobalSetting(key=GLOBAL_CATALOG_KEY, value=payload))
            else:
                row.value = payload
            if commit:
                db.commit()
            else:
                db.flush()
            return
        except (ProgrammingError, OperationalError) as exc:
            db.rollback()
            if attempt == 1 and _missing_global_settings_table(exc):
                ensure_app_global_settings_table()
                continue
            raise


def migrate_catalog_from_tenants_if_needed(db: Session) -> dict | None:
    """One-time: copy the richest tenant catalog into global when global is empty."""
    if load_raw_global_catalog(db) is not None:
        return None

    best: dict | None = None
    best_score = -1
    for tenant in db.query(Tenant).all():
        raw = (tenant.workflow_config or {}).get(CATALOG_KEY)
        if not isinstance(raw, dict):
            continue
        products = raw.get("products") or []
        packages = raw.get("packages") or []
        score = len(products) * 10 + len(packages)
        photo_bonus = sum(1 for p in products if p.get("image_ids") or p.get("image_id"))
        score += photo_bonus * 5
        if score > best_score:
            best_score = score
            best = raw

    if best is None:
        return None
    save_raw_global_catalog(db, best)
    return best


def ensure_global_catalog_dict(db: Session) -> dict:
    """Return global catalog dict, migrating from tenant or seeding defaults if needed."""
    from app.livewell.catalog_service import normalize_catalog

    raw = load_raw_global_catalog(db)
    if raw is None:
        migrated = migrate_catalog_from_tenants_if_needed(db)
        raw = migrated if migrated is not None else None
    if raw is None:
        raw = deepcopy(DEFAULT_CATALOG)
        try:
            save_raw_global_catalog(db, normalize_catalog(raw))
            raw = load_raw_global_catalog(db) or deepcopy(DEFAULT_CATALOG)
        except (ProgrammingError, OperationalError):
            db.rollback()
            return normalize_catalog(deepcopy(DEFAULT_CATALOG))
    try:
        from app.livewell.catalog_link_fixes import apply_link_fixes_once

        raw = apply_link_fixes_once(db, raw)
    except (ProgrammingError, OperationalError):
        db.rollback()
    return raw
