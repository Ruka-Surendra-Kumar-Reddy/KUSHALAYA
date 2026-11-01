"""One-off data fix: pre-rename product names in stored catalogs.

The assessment product was seeded as "Kushalaya Assessment (LWA)" before the
brand rename, and some rows still say "LiveWell360 Assessment (KAA)". Code and
seed files now say "Kushalaya Assessment (KAA)", but the catalog lives in the
database (app_global_settings.home_safety_catalog, plus any legacy copy in
tenant.workflow_config), so a deploy alone does not touch it.

Three passes, all idempotent (re-running is a no-op):

1. SVC-001 (the assessment service) whose name / short_description still
   contains "LiveWell" is reset to the factory copy in default_catalog.json.
2. "LiveWell360 Assessment (KAA)" / "(LWA)" -> "Kushalaya Assessment (KAA)"
   in every string value of the catalog and of the other workflow_config
   entries (ids and keys are never changed).
3. Whole-word "LWA" not followed by "_" -> "KAA" in catalog string values.

Usage (from backend/, with the venv active):
    python -m scripts.rename_lwa_to_kaa             # dry run: report only
    python -m scripts.rename_lwa_to_kaa --dry-run   # same, explicit
    python -m scripts.rename_lwa_to_kaa --apply     # write changes
"""

from __future__ import annotations

import re
import sys
from typing import Any

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SessionLocal
from app.livewell.catalog_defaults import DEFAULT_CATALOG
from app.livewell.config_keys import CATALOG_KEY
from app.livewell.global_catalog_store import load_raw_global_catalog, save_raw_global_catalog
from app.models.tenant import Tenant

WORD = re.compile(r"\bLWA\b(?!_)")

# The owner's spelling of the brand (capital A). The catalog is served to the
# ops UI unbranded, so this must be the final display string, not a token.
BRAND = "KushAlaya"

# Any earlier spelling of the product title -> the current one.
BRAND_TITLE = re.compile(r"(?:LiveWell360|Kushalaya|KushAlaya)\s+Assessment\s+\((?:KAA|LWA)\)")
BRAND_TITLE_NEW = f"{BRAND} Assessment (KAA)"


def brand_spelling(value: str) -> str:
    """Factory seed files use the lower-case 'Kushalaya'; the DB must carry the owner's spelling."""
    return value.replace("Kushalaya", BRAND)

ASSESSMENT_PRODUCT_CODE = "SVC-001"
ASSESSMENT_PRODUCT_ID = "prod_svc_001"
FACTORY_RESET_FIELDS = ("name", "short_description")


def rename_in(value, path: str, changes: list[str], *, lwa: bool = True):
    """Return `value` with the brand title (and, when `lwa`, LWA -> KAA) in every string."""
    if isinstance(value, str):
        new = BRAND_TITLE.sub(BRAND_TITLE_NEW, value)
        if lwa:
            new = WORD.sub("KAA", new)
        if new != value:
            changes.append(f"{path}: {value!r} -> {new!r}")
        return new
    if isinstance(value, list):
        return [rename_in(v, f"{path}[{i}]", changes, lwa=lwa) for i, v in enumerate(value)]
    if isinstance(value, dict):
        # Values only — keys such as product ids stay as they are.
        return {k: rename_in(v, f"{path}.{k}", changes, lwa=lwa) for k, v in value.items()}
    return value


def _factory_assessment_product() -> dict[str, Any] | None:
    for product in DEFAULT_CATALOG.get("products", []):
        if product.get("product_code") == ASSESSMENT_PRODUCT_CODE or product.get("id") == ASSESSMENT_PRODUCT_ID:
            return product
    return None


def reset_assessment_product(catalog: dict, path: str, changes: list[str]) -> dict:
    """Reset SVC-001 name/short_description to factory copy when they still say LiveWell."""
    factory = _factory_assessment_product()
    if factory is None:
        return catalog
    products = catalog.get("products")
    if not isinstance(products, list):
        return catalog
    out_products = []
    for i, product in enumerate(products):
        if not isinstance(product, dict) or (
            product.get("product_code") != ASSESSMENT_PRODUCT_CODE
            and product.get("id") != ASSESSMENT_PRODUCT_ID
        ):
            out_products.append(product)
            continue
        fixed = dict(product)
        for field in FACTORY_RESET_FIELDS:
            current = fixed.get(field)
            if isinstance(current, str) and "LiveWell" in current and factory.get(field):
                target = brand_spelling(str(factory[field]))
                changes.append(f"{path}.products[{i}].{field}: {current!r} -> {target!r} (factory)")
                fixed[field] = target
        out_products.append(fixed)
    return {**catalog, "products": out_products}


def fix_catalog(raw: dict, path: str, changes: list[str]) -> dict:
    """All catalog passes: factory reset of SVC-001, brand title, LWA -> KAA."""
    return rename_in(reset_assessment_product(raw, path, changes), path, changes)


def fix_workflow_config(cfg: dict, path: str, changes: list[str]) -> dict:
    """Catalog copy gets the full treatment; every other value only the brand title."""
    out = {}
    for key, value in cfg.items():
        if key == CATALOG_KEY and isinstance(value, dict):
            out[key] = fix_catalog(value, f"{path}.{key}", changes)
        else:
            out[key] = rename_in(value, f"{path}.{key}", changes, lwa=False)
    return out


def main(argv: list[str]) -> int:
    apply = "--apply" in argv
    dry_run = "--dry-run" in argv
    if apply and dry_run:
        print("Pass either --apply or --dry-run, not both.", file=sys.stderr)
        return 2
    db = SessionLocal()
    try:
        total = 0

        raw = load_raw_global_catalog(db)
        if raw is not None:
            changes: list[str] = []
            fixed = fix_catalog(raw, "global", changes)
            for line in changes:
                print(line)
            total += len(changes)
            if changes and apply:
                save_raw_global_catalog(db, fixed)

        for tenant in db.query(Tenant).all():
            cfg = tenant.workflow_config
            if not isinstance(cfg, dict) or not cfg:
                continue
            changes = []
            fixed = fix_workflow_config(cfg, f"tenant[{tenant.id}]", changes)
            for line in changes:
                print(line)
            total += len(changes)
            if changes and apply:
                tenant.workflow_config = fixed
                flag_modified(tenant, "workflow_config")
                db.commit()

        print(f"{'applied' if apply else 'would change'}: {total} string(s)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
