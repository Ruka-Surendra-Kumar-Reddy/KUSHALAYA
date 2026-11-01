#!/usr/bin/env python3
"""Build Kushalaya_Configuration.xlsx from code defaults.

Catalog (products/packages) is preserved from the existing workbook when present —
the xlsx sheets 05/06/10/11 are the source of truth. Other engines still come from
JSON / Python defaults.

After editing catalog in the xlsx, sync JSON mirrors:

  python backend/scripts/sync_catalog_defaults_from_workbook.py

Full rebuild (non-catalog sheets from code):

  python backend/scripts/build_master_workbook.py
  python backend/scripts/validate_master_workbook.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.livewell.ai_defaults import DEFAULT_AI_CONFIG
from app.livewell.catalog_defaults import DEFAULT_CATALOG
from app.livewell.master_data_workbook import (
    build_payload_from_sheets,
    export_workbook_bytes,
    parse_workbook_bytes,
)
from app.livewell.pricing_defaults import DEFAULT_PRICING
from app.livewell.rubric_defaults import DEFAULT_RUBRIC
from app.livewell.rule_engine_defaults import default_rule_engine_payload
from app.livewell.solution_service import DEFAULT_SOLUTIONS
from app.livewell.supplier_defaults import DEFAULT_SUPPLIERS

DATA_DIR = BACKEND / "app" / "livewell" / "data"
CANONICAL_MASTER_WORKBOOK = DATA_DIR / "Kushalaya_Configuration.xlsx"


def _catalog_from_existing_workbook() -> dict | None:
    if not CANONICAL_MASTER_WORKBOOK.is_file():
        return None
    try:
        sheets = parse_workbook_bytes(CANONICAL_MASTER_WORKBOOK.read_bytes())
        payload = build_payload_from_sheets(sheets)
    except Exception as exc:  # noqa: BLE001
        print(f"WARN: could not read catalog from existing xlsx ({exc}); using DEFAULT_CATALOG")
        return None
    catalog = payload.get("catalog") or {}
    if not (catalog.get("products") or []):
        return None
    return catalog


def main() -> None:
    catalog = _catalog_from_existing_workbook() or DEFAULT_CATALOG
    src = "existing xlsx" if catalog is not DEFAULT_CATALOG else "DEFAULT_CATALOG JSON"
    payload = {
        "rubric": DEFAULT_RUBRIC,
        "solutions": DEFAULT_SOLUTIONS,
        "catalog": catalog,
        "pricing": DEFAULT_PRICING,
        "suppliers": DEFAULT_SUPPLIERS,
        "ai_config": DEFAULT_AI_CONFIG,
        "rule_engine": default_rule_engine_payload(),
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    raw = export_workbook_bytes(
        payload,
        meta={
            "upload_id": "",
            "uploaded_at": "",
            "exported_at": now,
            "tenant_id": "",
        },
    )
    tmp = CANONICAL_MASTER_WORKBOOK.with_suffix(".xlsx.tmp")
    tmp.write_bytes(raw)
    try:
        tmp.replace(CANONICAL_MASTER_WORKBOOK)
    except PermissionError:
        print(
            f"WARN: could not replace {CANONICAL_MASTER_WORKBOOK} (file locked). "
            f"Wrote {tmp} — close Excel and rename/replace manually."
        )
        return
    n_prod = len((catalog.get("products") or []))
    n_pkg = len((catalog.get("packages") or []))
    print(f"Wrote {CANONICAL_MASTER_WORKBOOK} (catalog from {src}: {n_prod} products, {n_pkg} packages)")


if __name__ == "__main__":
    main()
