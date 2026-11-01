#!/usr/bin/env python3
"""Export products/packages from Kushalaya_Configuration.xlsx into JSON defaults.

The spreadsheet is the source of truth for catalog. Run after editing sheets
05_Products / 06_ProductSolutions / 10_Packages / 11_PackageProducts:

  python backend/scripts/sync_catalog_defaults_from_workbook.py

Writes:
  - backend/app/livewell/default_catalog.json
  - frontend/lib/livewell/generated/catalog-from-workbook.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.livewell.master_data_workbook import build_payload_from_sheets, parse_workbook_bytes
from app.livewell.seed_service import CANONICAL_MASTER_WORKBOOK

OUT_BACKEND = BACKEND / "app" / "livewell" / "default_catalog.json"
OUT_FRONTEND = REPO / "frontend" / "lib" / "livewell" / "generated" / "catalog-from-workbook.json"


def _catalog_from_workbook() -> dict:
    if not CANONICAL_MASTER_WORKBOOK.is_file():
        raise SystemExit(f"Missing workbook: {CANONICAL_MASTER_WORKBOOK}")
    sheets = parse_workbook_bytes(CANONICAL_MASTER_WORKBOOK.read_bytes())
    payload = build_payload_from_sheets(sheets)
    catalog = payload.get("catalog") or {}
    products = catalog.get("products") or []
    packages = catalog.get("packages") or []
    if not products:
        raise SystemExit("Workbook parsed but catalog.products is empty")
    return {"products": products, "packages": packages}


def main() -> None:
    catalog = _catalog_from_workbook()
    text = json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
    OUT_BACKEND.write_text(text, encoding="utf-8")
    OUT_FRONTEND.parent.mkdir(parents=True, exist_ok=True)
    OUT_FRONTEND.write_text(text, encoding="utf-8")
    print(
        f"Wrote {OUT_BACKEND} and {OUT_FRONTEND} "
        f"({len(catalog['products'])} products, {len(catalog['packages'])} packages)"
    )


if __name__ == "__main__":
    main()
