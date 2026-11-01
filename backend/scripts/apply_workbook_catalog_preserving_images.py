#!/usr/bin/env python3
"""Apply Kushalaya_Configuration.xlsx catalog into the global catalog.

Preserves existing product photos and rich fields when the workbook leaves
ImageDocumentIDs (and other DB-only columns) blank — same merge as Master Data
Approve.

  cd backend
  python scripts/apply_workbook_catalog_preserving_images.py
  python scripts/apply_workbook_catalog_preserving_images.py --dry-run
  python scripts/apply_workbook_catalog_preserving_images.py --tenant-id 1
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal
from app.livewell.catalog_image_service import HomeSafetyCatalogImageService
from app.livewell.catalog_images import normalize_image_ids
from app.livewell.catalog_service import merge_catalog_workbook_import, normalize_catalog
from app.livewell.config_keys import CATALOG_KEY
from app.livewell.global_catalog_store import load_raw_global_catalog, save_raw_global_catalog
from app.livewell.seed_service import load_canonical_payload
from app.models.tenant import Tenant
from sqlalchemy.orm.attributes import flag_modified

logger = logging.getLogger("apply_workbook_catalog")


def _photo_count(catalog: dict | None) -> int:
    products = (catalog or {}).get("products") or []
    return sum(1 for p in products if normalize_image_ids(p))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show merge photo preview only; do not write the database",
    )
    parser.add_argument(
        "--tenant-id",
        type=int,
        default=None,
        help="Also write merged catalog into this tenant workflow_config (optional)",
    )
    parser.add_argument(
        "--confirm-photo-loss",
        action="store_true",
        help="Allow write even if products-with-photos count would drop",
    )
    args = parser.parse_args()

    incoming = normalize_catalog(load_canonical_payload().get("catalog") or {})
    db = SessionLocal()
    try:
        previous = normalize_catalog(load_raw_global_catalog(db) or {"products": [], "packages": []})
        merged = merge_catalog_workbook_import(incoming, previous)
        before = _photo_count(previous)
        after = _photo_count(merged)
        print(
            f"Catalog merge preview: {len(previous.get('products') or [])} -> "
            f"{len(merged.get('products') or [])} products; "
            f"photos {before} -> {after}; "
            f"packages {len(merged.get('packages') or [])}"
        )
        for code in ("SMT-006", "SMT-011"):
            row = next((p for p in merged["products"] if p.get("product_code") == code), None)
            if row:
                print(
                    f"  {code}: {row.get('name')} "
                    f"(images={normalize_image_ids(row)})"
                )

        if after < before and not args.confirm_photo_loss:
            raise SystemExit(
                f"Refusing to write: photos would drop {before} -> {after}. "
                "Re-export live workbook ImageDocumentIDs or pass --confirm-photo-loss."
            )

        if args.dry_run:
            print("Dry run - no DB write.")
            return

        merged, relinked = HomeSafetyCatalogImageService.relink_orphaned_images(db, merged)
        if relinked:
            print(f"Relinked orphaned photos on {relinked} product(s)")
        after_relink = _photo_count(merged)
        save_raw_global_catalog(db, merged, commit=False)
        print(
            f"Saved global catalog: {len(merged['products'])} products, "
            f"{len(merged['packages'])} packages, {after_relink} with photos"
        )

        tenant_ids: list[int] = []
        if args.tenant_id is not None:
            tenant_ids = [args.tenant_id]
        else:
            # Mirror into every tenant that already has a catalog key (keeps Master Data UI in sync).
            for t in db.query(Tenant).all():
                cfg = t.workflow_config or {}
                if isinstance(cfg.get(CATALOG_KEY), dict):
                    tenant_ids.append(int(t.id))

        for tid in tenant_ids:
            tenant = db.query(Tenant).filter(Tenant.id == tid).first()
            if not tenant:
                print(f"WARN: tenant {tid} not found — skipped")
                continue
            cfg = dict(tenant.workflow_config or {})
            cfg[CATALOG_KEY] = merged
            tenant.workflow_config = cfg
            flag_modified(tenant, "workflow_config")
            print(f"Updated tenant {tid} workflow_config catalog")

        db.commit()
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
