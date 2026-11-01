#!/usr/bin/env python3
"""Re-link orphaned catalog image Documents to products (after Reset defaults wiped image_ids).

Usage (from backend/):
  python scripts/relink_catalog_product_photos.py --confirm
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Write re-linked image_ids back to the global catalog",
    )
    args = parser.parse_args()

    from app.core.database import SessionLocal
    from app.livewell.catalog_image_service import HomeSafetyCatalogImageService
    from app.livewell.catalog_service import normalize_catalog
    from app.livewell.global_catalog_store import (
        ensure_global_catalog_dict,
        save_raw_global_catalog,
    )

    db = SessionLocal()
    try:
        catalog = normalize_catalog(ensure_global_catalog_dict(db))
        before = sum(1 for p in catalog["products"] if p.get("image_ids"))
        updated, changed = HomeSafetyCatalogImageService.relink_orphaned_images(db, catalog)
        after = sum(1 for p in updated["products"] if p.get("image_ids"))
        print(f"Products with photos before: {before}")
        print(f"Products re-linked: {changed}")
        print(f"Products with photos after: {after}")
        if not args.confirm:
            print("Dry run only — pass --confirm to save.")
            return 0
        save_raw_global_catalog(db, updated)
        print("Saved global catalog.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
