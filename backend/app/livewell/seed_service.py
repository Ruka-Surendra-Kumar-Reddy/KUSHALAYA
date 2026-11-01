"""Seed tenant config from the canonical Kushalaya_Configuration.xlsx (version-controlled)."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.livewell.config_keys import CONFIG_KEYS, MASTER_BASELINE_KEY
from app.livewell.master_data_workbook import build_payload_from_sheets, parse_workbook_bytes
from app.livewell.stored_config import entity_is_empty, normalize_entity_config, read_stored_config
from app.models.tenant import Tenant

CANONICAL_MASTER_WORKBOOK = (
    Path(__file__).resolve().parent / "data" / "Kushalaya_Configuration.xlsx"
)


def load_canonical_workbook_bytes() -> bytes:
    if not CANONICAL_MASTER_WORKBOOK.is_file():
        raise FileNotFoundError(
            f"Canonical master workbook not found at {CANONICAL_MASTER_WORKBOOK}. "
            "Ensure Kushalaya_Configuration.xlsx is present under app/livewell/data/."
        )
    return CANONICAL_MASTER_WORKBOOK.read_bytes()


def load_canonical_payload() -> dict:
    """Parse the shipped master spreadsheet into workflow_config-shaped payloads."""
    sheets = parse_workbook_bytes(load_canonical_workbook_bytes())
    return build_payload_from_sheets(sheets)


def seed_missing_defaults(cfg: dict, *, only: tuple[str, ...] | None = None) -> tuple[dict, list[str]]:
    """Fill empty entities from the canonical master spreadsheet."""
    from app.livewell.master_data_service import _validate_payload

    errors: list[str] = []
    warnings: list[str] = []
    cleaned = _validate_payload(load_canonical_payload(), errors, warnings)
    if errors:
        raise ValueError("; ".join(errors))

    updated = dict(cfg or {})
    current = read_stored_config(updated)
    seeded: list[str] = []
    targets = only or tuple(CONFIG_KEYS.keys())

    for entity in targets:
        if entity not in cleaned:
            continue
        data = current.get(entity) or {}
        if not entity_is_empty(entity, data):
            continue
        payload = cleaned[entity]
        if entity_is_empty(entity, payload):
            continue
        updated[CONFIG_KEYS[entity]] = payload
        seeded.append(entity)
        current[entity] = payload

    return updated, seeded


def _ensure_seed_baseline(cfg: dict, *, seeded: list[str]) -> str | None:
    """Stamp spreadsheet sync baseline after factory seed so dirty tracking works."""
    existing = cfg.get(MASTER_BASELINE_KEY)
    if isinstance(existing, dict) and existing.get("upload_id") and existing.get("baseline"):
        return None

    live = normalize_entity_config(read_stored_config(cfg))
    has_content = any(not entity_is_empty(e, live.get(e) or {}) for e in CONFIG_KEYS)
    if not has_content:
        return None

    upload_id = f"md-seed-{uuid.uuid4().hex[:10]}"
    cfg[MASTER_BASELINE_KEY] = {
        "upload_id": upload_id,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "exported_at": None,
        "baseline": deepcopy(live),
        "source": "factory_seed",
    }
    return upload_id


def seed_tenant_defaults(db: Session, tenant: Tenant, *, only: tuple[str, ...] | None = None) -> list[str]:
    """
    Fill empty master-data entities from Kushalaya_Configuration.xlsx and stamp
    a baseline UploadId (md-seed-*) so Master Data dirty/export sync works.
    """
    cfg, seeded = seed_missing_defaults(dict(tenant.workflow_config or {}), only=only)
    upload_id = _ensure_seed_baseline(cfg, seeded=seeded)
    if not seeded and not upload_id:
        return []

    if "catalog" in seeded:
        from app.livewell.catalog_service import normalize_catalog
        from app.livewell.config_keys import CATALOG_KEY
        from app.livewell.global_catalog_store import load_raw_global_catalog, save_raw_global_catalog

        if load_raw_global_catalog(db) is None and isinstance(cfg.get(CATALOG_KEY), dict):
            from app.livewell.catalog_link_fixes import mark_link_fixes_current

            mark_link_fixes_current(db, "seeded from current defaults")
            save_raw_global_catalog(db, normalize_catalog(cfg[CATALOG_KEY]), commit=False)

    tenant.workflow_config = cfg
    flag_modified(tenant, "workflow_config")
    db.commit()
    db.refresh(tenant)
    if upload_id:
        seeded = list(seeded) + [f"baseline:{upload_id}"]
    return seeded
