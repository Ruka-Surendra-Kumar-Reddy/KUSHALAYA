"""One-time correction of assessment finding -> product links in the live catalog.

The live catalog is the global ``app_global_settings['home_safety_catalog']`` row,
seeded once from default_catalog.json, so fixing the seed alone does not reach
production. ``apply_link_fixes_once`` runs from the catalog loader: it rewrites
only ``solution_ids`` on the products below (prices, images and copy untouched),
adds EMG-006 / SMT-012 / SMT-011 from the seed if missing, logs what changed and records a
marker so later admin edits are never overwritten.

v3 (2026-10-11) only adds: BTH-012/013 and HLT-001..004 from the seed if missing (moved
out of the shop-only list), their missing solution links, and the HLT catalog type. A
catalog already at v2 gets only the v3 step, so admin edits since v2 are kept.

Audit: docs/ASSESSMENT_PRODUCT_LINKS.md (2026-10-09).
"""

from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime, timezone

from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

LINK_FIXES_KEY = "catalog_link_fixes"
LINK_FIXES_VERSION = 3  # v2: add SMT-011; v3: add BTH-012/013, HLT-001..004 (+ links, HLT type)

# product_code -> corrected solution_ids (same as default_catalog.json).
LINK_FIXES: dict[str, list[str]] = {
    "BTH-001": ["LW-HS-BTH-001", "LW-HS-BTH-002"],
    "BTH-003": ["LW-HS-BTH-002", "LW-HS-BTH-007"],
    "BTH-011": ["LW-HS-BTH-011"],
    "BTH-009": ["LW-HS-BTH-004", "LW-HS-BTH-002", "LW-HS-STA-001"],
    "BTH-010": ["LW-HS-BTH-002", "LW-HS-BTH-003"],
    "BED-004": ["LW-HS-BED-002"],
    "LIV-003": ["LW-HS-LIV-001"],
    "EXT-002": ["LW-HS-ENT-001", "LW-HS-ENT-004", "LW-HS-BTH-007", "LW-MOB-WCH-001"],
    "HAL-001": ["LW-HS-BED-002", "LW-TECH-LIT-001"],
    "HAL-002": ["LW-HS-BED-002"],
    "HAL-003": ["LW-HS-BED-002"],
    "KIT-001": ["LW-IADL-MEAL-001"],
    "KIT-002": ["LW-IADL-MEAL-001"],
    "BAL-001": ["LW-HS-ENT-001"],
    "BAL-002": ["LW-HS-ENT-002"],
    "MOB-007": ["LW-HS-ENT-001", "LW-HS-ENT-004", "LW-MOB-WCH-001"],
    "SMT-001": ["LW-TECH-SEC-001"],
    "SMT-002": ["LW-TECH-FAL-001", "LW-TECH-SEC-001"],
    "SMT-003": ["LW-TECH-FAL-001", "LW-TECH-SEC-001"],
    "SMT-004": ["LW-TECH-FAL-001", "LW-COG-WAN-001"],
    "SMT-005": ["LW-COG-WAN-001", "LW-TECH-SEC-001"],
    "SMT-006": ["LW-EMG-PLN-001", "LW-EMG-COM-001", "LW-COG-WAN-001", "LW-TECH-FAL-001"],
    "SMT-007": ["LW-HL-MED-001", "LW-COG-MEM-001"],
    "SMT-008": ["LW-COG-MEM-001", "LW-TECH-LIT-001"],
    "SMT-009": ["LW-HM-PLB-001"],
    "SMT-010": ["LW-HS-LIV-004", "LW-HS-KIT-002"],
    "SMT-011": ["LW-EMG-COM-001", "LW-TECH-FAL-001"],
    "WEL-002": ["LW-WELL-AGE-001", "LW-SOC-LON-001", "LW-WELL-SOC-001"],
    "WEL-003": ["LW-HL-MED-001"],
    "WEL-004": ["LW-HL-MON-001", "LW-HC-PCP-001"],
    "WEL-005": ["LW-HL-NUT-001", "LW-IADL-SHOP-001"],
    "WEL-006": ["LW-SOC-LON-001", "LW-FAM-COM-001"],
    "WEL-010": ["LW-FAM-COM-001", "LW-EMG-PLN-001", "LW-FIN-GOV-001", "LW-FAM-ECM-001"],
    "WEL-013": ["LW-SOC-LON-001"],
    "HM-001": ["LW-HM-ELE-001", "LW-HS-LIV-004"],
    "HM-005": ["LW-HM-ELE-001", "LW-HS-LIV-004"],
    "NUR-004": ["LW-HL-MED-001"],
    "NUR-005": [],
    "NUR-006": [],
    "NUR-007": [],
    "PHY-001": ["LW-MOB-WAL-001", "LW-MOB-BAL-001", "LW-HC-PT-001"],
    "PHY-002": ["LW-MOB-WAL-001", "LW-MOB-BAL-001", "LW-HC-PT-001"],
    "PHY-003": ["LW-MOB-WAL-001", "LW-MOB-BAL-001", "LW-HC-PT-001"],
    "DX-001": ["LW-HL-MON-001", "LW-HC-PCP-001"],
    "TRN-001": ["LW-HC-PCP-001"],
    "TRN-002": ["LW-HC-PCP-001"],
    "TRN-003": [],
    "EMG-006": ["LW-EMG-COM-001"],
    "SMT-012": ["LW-COG-WAN-001"],
}

# Products the corrected links need that older live catalogs lack (copied from the seed).
ADDED_PRODUCT_CODES = ("EMG-006", "SMT-012", "SMT-011")

# v3: products added if missing; solution ids appended if missing (never removed).
V3_PRODUCT_LINKS: dict[str, list[str]] = {
    "BTH-012": ["LW-HS-BTH-002", "LW-HS-BTH-003"],
    "BTH-013": ["LW-HS-BTH-010"],
    "HLT-001": ["LW-HL-MON-001"],
    "HLT-002": ["LW-HL-MON-001"],
    "HLT-003": ["LW-HL-MON-001"],
    "HLT-004": ["LW-HL-MED-001", "LW-COG-MEM-001"],
}
V3_CATEGORY_TYPE = {"prefix": "HLT", "label": "Health Monitoring", "kind": "product", "sort": 18, "active": True}


def apply_link_fixes(catalog: dict) -> tuple[dict, list[str]]:
    """Return (catalog with corrected links, change log). Idempotent; touches only solution_ids."""
    from app.livewell.catalog_defaults import DEFAULT_CATALOG

    out = deepcopy(catalog or {})
    products = out.setdefault("products", [])
    changes: list[str] = []
    codes = {str(p.get("product_code") or "") for p in products}
    seed = {p.get("product_code"): p for p in DEFAULT_CATALOG.get("products") or []}
    for code in ADDED_PRODUCT_CODES:
        if code not in codes and code in seed:
            products.append(deepcopy(seed[code]))
            changes.append(f"{code}: added from seed")
    for product in products:
        code = str(product.get("product_code") or "")
        if code not in LINK_FIXES:
            continue
        before = list(product.get("solution_ids") or [])
        after = list(LINK_FIXES[code])
        if before != after:
            product["solution_ids"] = after
            changes.append(f"{code}: {before} -> {after}")
    return out, changes


def apply_v3_additions(catalog: dict) -> tuple[dict, list[str]]:
    """Add the v3 products / links / HLT type if missing. Idempotent; never removes or rewrites."""
    from app.livewell.catalog_defaults import DEFAULT_CATALOG

    out = deepcopy(catalog or {})
    products = out.setdefault("products", [])
    changes: list[str] = []
    by_code = {str(p.get("product_code") or ""): p for p in products}
    seed = {p.get("product_code"): p for p in DEFAULT_CATALOG.get("products") or []}
    for code, links in V3_PRODUCT_LINKS.items():
        product = by_code.get(code)
        if product is None:
            if code not in seed:
                continue
            product = deepcopy(seed[code])
            product["solution_ids"] = list(links)
            products.append(product)
            changes.append(f"{code}: added from seed")
            continue
        before = list(product.get("solution_ids") or [])
        after = before + [s for s in links if s not in before]
        if after != before:
            product["solution_ids"] = after
            changes.append(f"{code}: {before} -> {after}")
    types = out.get("category_types")
    if isinstance(types, list) and types and not any(
        isinstance(t, dict) and str(t.get("prefix") or "").upper() == "HLT" for t in types
    ):
        types.append(dict(V3_CATEGORY_TYPE))
        changes.append("category type HLT: added")
    return out, changes


def mark_link_fixes_current(db: Session, reason: str) -> None:
    """An admin wrote the global catalog (save / workbook approve / seed): record the fix as
    done so it can never rewrite that catalog later. Caller commits."""
    from app.models.app_global_setting import AppGlobalSetting

    value = {
        "version": LINK_FIXES_VERSION,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "changes": 0,
        "superseded_by": reason,
    }
    marker = db.get(AppGlobalSetting, LINK_FIXES_KEY)
    if marker is None:
        db.add(AppGlobalSetting(key=LINK_FIXES_KEY, value=value))
    elif not (isinstance(marker.value, dict) and int(marker.value.get("version") or 0) >= LINK_FIXES_VERSION):
        marker.value = value


def apply_link_fixes_once(db: Session, raw: dict) -> dict:
    """Apply LINK_FIXES to the stored global catalog the first time it is loaded."""
    from app.livewell.global_catalog_store import save_raw_global_catalog
    from app.models.app_global_setting import AppGlobalSetting

    marker = db.get(AppGlobalSetting, LINK_FIXES_KEY)
    done = int(marker.value.get("version") or 0) if marker and isinstance(marker.value, dict) else 0
    if done >= LINK_FIXES_VERSION:
        return raw
    fixed, changes = (raw, []) if done >= 2 else apply_link_fixes(raw)
    fixed, more = apply_v3_additions(fixed)
    changes += more
    if changes:
        save_raw_global_catalog(db, fixed, commit=False)
    value = {
        "version": LINK_FIXES_VERSION,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "changes": len(changes),
    }
    if marker is None:
        db.add(AppGlobalSetting(key=LINK_FIXES_KEY, value=value))
    else:
        marker.value = value
    db.commit()
    for line in changes:
        log.info("catalog link fix: %s", line)
    log.info("catalog link fixes v%s applied: %d change(s)", LINK_FIXES_VERSION, len(changes))
    return fixed
