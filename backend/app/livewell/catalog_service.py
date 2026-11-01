"""Safe Home product catalog — global (shared across tenants)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.rbac import assert_tenant_access, resolve_tenant_id, WRITE_ROLES
from app.core.responses import raise_bad_request
from app.livewell.catalog_images import image_url_for, normalize_image_ids
from app.livewell.commerce import catalog_image_url
from app.livewell.catalog_types import resolve_category_types
from app.livewell.global_catalog_store import (
    ensure_global_catalog_dict,
    save_raw_global_catalog,
)
from app.livewell.workbook_format import normalize_category_prefix, parse_money_inr
from app.models.document import Document
from app.models.tenant import Tenant
from app.models.user import User

HOME_SAFETY_CATALOG_IMAGE = "HOME_SAFETY_CATALOG_IMAGE"


def _existing_catalog_image_ids(db: Session, candidate_ids: list[int]) -> set[int]:
    """Keep only document IDs that exist as catalog images (any tenant audit row)."""
    if not candidate_ids:
        return set()
    rows = (
        db.query(Document.id)
        .filter(
            Document.document_type == HOME_SAFETY_CATALOG_IMAGE,
            Document.id.in_(candidate_ids),
        )
        .all()
    )
    return {int(r[0]) for r in rows}


def _catalog_image_meta(db: Session, candidate_ids: list[int]) -> dict[int, dict]:
    """Map document_id → {supplier_id} from Document.ocr_extracted_json."""
    if not candidate_ids:
        return {}
    rows = (
        db.query(Document.id, Document.ocr_extracted_json)
        .filter(
            Document.document_type == HOME_SAFETY_CATALOG_IMAGE,
            Document.id.in_(candidate_ids),
        )
        .all()
    )
    out: dict[int, dict] = {}
    for doc_id, ocr in rows:
        meta = ocr if isinstance(ocr, dict) else {}
        raw_sid = meta.get("supplier_id")
        supplier_id = str(raw_sid).strip() if raw_sid not in (None, "") else None
        out[int(doc_id)] = {"supplier_id": supplier_id}
    return out


def overlay_factory_copy_for_legacy_labor(catalog: dict) -> dict:
    """Replace labor-only / 'billed separately' product & package copy from factory defaults."""
    import re

    from app.livewell.catalog_defaults import DEFAULT_CATALOG

    legacy_re = re.compile(
        r"billed separately|products extra|\(labor\)|install labor|project \(labor\)|labor \+ product",
        re.I,
    )
    pkg_legacy_re = re.compile(
        r"billed separately|billed separately or bundled|partner-rate",
        re.I,
    )

    default_products = {
        str(p.get("id")): p for p in (DEFAULT_CATALOG.get("products") or []) if p.get("id")
    }
    default_packages = {
        str(p.get("id")): p for p in (DEFAULT_CATALOG.get("packages") or []) if p.get("id")
    }

    products = []
    for product in catalog.get("products") or []:
        pid = str(product.get("id") or "")
        factory = default_products.get(pid)
        if not factory:
            products.append(product)
            continue
        blob = " ".join(
            str(product.get(k) or "")
            for k in ("name", "short_description", "price_label", "details", "purpose")
        )
        if not legacy_re.search(blob):
            products.append(product)
            continue
        products.append(
            {
                **product,
                "name": factory.get("name") or product.get("name"),
                "short_description": factory.get("short_description")
                or product.get("short_description"),
                "details": factory.get("details") or product.get("details"),
                "purpose": factory.get("purpose") or product.get("purpose"),
                "price_label": factory.get("price_label") or product.get("price_label"),
                "price_inr": factory.get("price_inr")
                if factory.get("price_inr") is not None
                else product.get("price_inr"),
                "installed_price": factory.get("installed_price")
                or product.get("installed_price"),
                "product_cost": factory.get("product_cost") or product.get("product_cost"),
            }
        )

    packages = []
    for package in catalog.get("packages") or []:
        pkg_id = str(package.get("id") or "")
        factory = default_packages.get(pkg_id)
        if not factory:
            packages.append(package)
            continue
        if not pkg_legacy_re.search(str(package.get("description") or "")):
            packages.append(package)
            continue
        packages.append(
            {
                **package,
                "name": factory.get("name") or package.get("name"),
                "tagline": factory.get("tagline") or package.get("tagline"),
                "description": factory.get("description") or package.get("description"),
                "price_label": factory.get("price_label") or package.get("price_label"),
                "price_inr": factory.get("price_inr")
                if factory.get("price_inr") is not None
                else package.get("price_inr"),
            }
        )

    return {**catalog, "products": products, "packages": packages}


def enrich_catalog(
    catalog: dict,
    *,
    existing_image_ids: set[int] | None = None,
    image_meta: dict[int, dict] | None = None,
) -> dict:
    products = []
    for product in catalog.get("products") or []:
        image_ids = list(product.get("image_ids") or [])
        if existing_image_ids is not None:
            image_ids = [i for i in image_ids if i in existing_image_ids]
        image_urls = [image_url_for(image_id) for image_id in image_ids]
        images = []
        for image_id in image_ids:
            meta = (image_meta or {}).get(int(image_id)) or {}
            supplier_id = meta.get("supplier_id")
            images.append(
                {
                    "document_id": int(image_id),
                    "url": image_url_for(image_id),
                    "supplier_id": supplier_id,
                    "photo_kind": "vendor" if supplier_id else "generic",
                }
            )
        products.append(
            {
                **product,
                "image_ids": image_ids,
                "image_urls": image_urls,
                "images": images,
                "image_id": image_ids[0] if image_ids else None,
                # No uploaded photo yet: the reference picture shipped with the site.
                "image_url": image_urls[0] if image_urls else catalog_image_url(product.get("product_code")),
            }
        )
    return {**catalog, "products": products}


def _normalize_product(raw: dict, index: int = 0) -> dict:
    options = [str(x).strip() for x in raw.get("options") or [] if str(x).strip()]
    findings = [str(x).strip() for x in raw.get("assessment_findings") or [] if str(x).strip()]
    from app.livewell.solution_id_aliases import remap_solution_ids

    solution_ids = remap_solution_ids(
        [str(x).strip() for x in raw.get("solution_ids") or [] if str(x).strip()]
    )
    life = raw.get("life_years")
    code = str(raw.get("product_code", "")).strip()
    if code.lower() in ("none", "null", "n/a", "na"):
        code = ""
    return {
        "id": str(raw.get("id", "")),
        "product_code": code or None,
        "name": str(raw.get("name", "")).strip(),
        "short_description": str(raw.get("short_description", "")).strip(),
        "details": str(raw.get("details", "")).strip(),
        "category": str(raw.get("category", "General")).strip(),
        "category_prefix": normalize_category_prefix(raw.get("category_prefix")),
        "price_inr": parse_money_inr(raw.get("price_inr")),
        "price_label": str(raw.get("price_label", "")).strip() or "Quote",
        "sort_order": int(raw.get("sort_order", index)),
        "image_ids": normalize_image_ids(raw),
        "purpose": str(raw.get("purpose", "")).strip(),
        "options": options,
        "material": str(raw.get("material", "")).strip(),
        "installation_type": str(raw.get("installation_type", "")).strip(),
        "contractor_type": str(raw.get("contractor_type", "")).strip(),
        "install_time": str(raw.get("install_time", "")).strip(),
        "product_cost": str(raw.get("product_cost", "")).strip(),
        "installed_price": str(raw.get("installed_price", "")).strip(),
        "life_years": int(life) if life is not None and life != "" else None,
        "maintenance_schedule": str(raw.get("maintenance_schedule", "")).strip(),
        "assessment_findings": findings,
        "safety_improvement": max(0, int(raw.get("safety_improvement") or 0)),
        "solution_ids": solution_ids,
    }


def _normalize_package(raw: dict, valid_product_ids: set[str]) -> dict:
    product_ids = [pid for pid in raw.get("product_ids") or [] if pid in valid_product_ids]
    return {
        "id": str(raw.get("id", "")),
        "name": str(raw.get("name", "")).strip(),
        "tagline": str(raw.get("tagline", "")).strip(),
        "description": str(raw.get("description", "")).strip(),
        "price_inr": parse_money_inr(raw.get("price_inr")),
        "price_label": str(raw.get("price_label", "")).strip() or "From",
        "highlight": bool(raw.get("highlight")),
        "product_ids": product_ids,
        "sort_order": int(raw.get("sort_order", 0)),
    }


def normalize_catalog(raw: dict) -> dict:
    products = [
        _normalize_product(p, i) for i, p in enumerate(raw.get("products") or [])
    ]
    products = [p for p in products if p["id"] and p["name"]]
    products.sort(key=lambda p: p["sort_order"])
    valid_ids = {p["id"] for p in products}
    packages = [
        _normalize_package(pkg, valid_ids) for pkg in raw.get("packages") or []
    ]
    packages = [p for p in packages if p["id"] and p["name"]]
    packages.sort(key=lambda p: p["sort_order"])
    category_types = resolve_category_types(raw.get("category_types"), products)
    return {
        "products": products,
        "packages": packages,
        "category_types": category_types,
    }


def merge_catalog_workbook_import(incoming: dict, previous: dict) -> dict:
    """Preserve DB-only catalog fields when applying a thin workbook import."""
    prev_products = {
        str(p["id"]): p for p in (previous or {}).get("products") or [] if p.get("id")
    }
    prev_packages = {
        str(p["id"]): p for p in (previous or {}).get("packages") or [] if p.get("id")
    }

    product_text_fields = (
        "short_description",
        "details",
        "purpose",
        "material",
        "installation_type",
        "contractor_type",
        "install_time",
        "product_cost",
        "installed_price",
        "maintenance_schedule",
        "category_prefix",
    )
    product_list_fields = ("options", "assessment_findings")

    merged_products = []
    for product in incoming.get("products") or []:
        pid = str(product.get("id", ""))
        prev = prev_products.get(pid, {})

        incoming_ids = normalize_image_ids(product)
        prev_ids = normalize_image_ids(prev)
        if incoming_ids:
            product = {**product, "image_ids": incoming_ids}
        elif prev_ids:
            product = {**product, "image_ids": prev_ids}

        prev_solutions = list(prev.get("solution_ids") or [])
        if not product.get("solution_ids") and prev_solutions:
            product = {**product, "solution_ids": prev_solutions}

        for field in product_text_fields:
            incoming_val = str(product.get(field) or "").strip()
            prev_val = str(prev.get(field) or "").strip()
            if not incoming_val and prev_val:
                product = {**product, field: prev[field]}

        name = str(product.get("name") or "").strip()
        short = str(product.get("short_description") or "").strip()
        prev_short = str(prev.get("short_description") or "").strip()
        if short == name and prev_short and prev_short != name:
            product = {**product, "short_description": prev_short}

        for field in product_list_fields:
            if not product.get(field) and prev.get(field):
                product = {**product, field: list(prev[field])}

        if product.get("life_years") in (None, "") and prev.get("life_years") is not None:
            product = {**product, "life_years": prev["life_years"]}

        if not product.get("safety_improvement") and prev.get("safety_improvement"):
            product = {**product, "safety_improvement": prev["safety_improvement"]}

        merged_products.append(product)

    package_text_fields = ("tagline", "description", "price_label")
    merged_packages = []
    for package in incoming.get("packages") or []:
        pkg_id = str(package.get("id", ""))
        prev = prev_packages.get(pkg_id, {})
        for field in package_text_fields:
            if not str(package.get(field) or "").strip() and str(prev.get(field) or "").strip():
                package = {**package, field: prev[field]}
        if package.get("price_inr") in (None, "", 0) and prev.get("price_inr"):
            package = {**package, "price_inr": prev["price_inr"]}
        if not package.get("sort_order") and prev.get("sort_order"):
            package = {**package, "sort_order": prev["sort_order"]}
        if not package.get("product_ids") and prev.get("product_ids"):
            package = {**package, "product_ids": list(prev["product_ids"])}
        merged_packages.append(package)

    merged = {**incoming, "products": merged_products, "packages": merged_packages}
    incoming_types = incoming.get("category_types") or []
    previous_types = (previous or {}).get("category_types") or []
    if not incoming_types and previous_types:
        merged["category_types"] = list(previous_types)
    return merged


def merge_catalog_product_images(incoming: dict, previous: dict) -> dict:
    """Keep existing product image_ids when incoming rows omit them (e.g. workbook import)."""
    return merge_catalog_workbook_import(incoming, previous)


class HomeSafetyCatalogService:

    @staticmethod
    def _tenant(db: Session, user: User) -> Tenant:
        tid = resolve_tenant_id(user)
        if tid is None and user.tenant_id is not None:
            # SYSTEM_ADMIN: resolve_tenant_id ignores user.tenant_id unless passed
            # explicitly; seed/upload scripts set tenant_id on the actor.
            tid = int(user.tenant_id)
        if tid is None:
            raise_bad_request("Tenant required")
        tenant = db.query(Tenant).filter(Tenant.id == tid).first()
        if not tenant:
            raise_bad_request("Tenant not found")
        assert_tenant_access(user, tenant.id)
        return tenant

    @staticmethod
    def _assert_can_edit(user: User) -> None:
        if user.role not in WRITE_ROLES:
            raise_bad_request("Not allowed to edit catalog")

    @staticmethod
    def _enriched(db: Session, catalog: dict) -> dict:
        normalized = overlay_factory_copy_for_legacy_labor(normalize_catalog(catalog))
        candidate_ids = [
            int(image_id)
            for product in normalized.get("products") or []
            for image_id in product.get("image_ids") or []
        ]
        existing = _existing_catalog_image_ids(db, candidate_ids)
        meta = _catalog_image_meta(db, [i for i in candidate_ids if i in existing])
        return enrich_catalog(
            normalized,
            existing_image_ids=existing,
            image_meta=meta,
        )

    @staticmethod
    def get_catalog(
        db: Session,
        user: User | None,
        *,
        tenant_id: int | None = None,
    ) -> dict:
        """Return the global catalog. tenant_id is ignored (kept for API compatibility)."""
        del tenant_id
        if user is not None:
            HomeSafetyCatalogService._tenant(db, user)
        return HomeSafetyCatalogService._enriched(db, ensure_global_catalog_dict(db))

    @staticmethod
    def save_catalog(db: Session, user: User, catalog: dict) -> dict:
        HomeSafetyCatalogService._tenant(db, user)
        HomeSafetyCatalogService._assert_can_edit(user)

        previous = normalize_catalog(ensure_global_catalog_dict(db))
        normalized = merge_catalog_workbook_import(normalize_catalog(catalog), previous)
        normalized = overlay_factory_copy_for_legacy_labor(normalized)

        if not normalized["products"]:
            raise_bad_request("At least one product is required")

        from app.livewell.catalog_image_service import HomeSafetyCatalogImageService

        normalized, _relinked = HomeSafetyCatalogImageService.relink_orphaned_images(
            db, normalized
        )

        from app.livewell.catalog_link_fixes import mark_link_fixes_current

        mark_link_fixes_current(db, "admin catalog save")
        save_raw_global_catalog(db, normalized)
        return HomeSafetyCatalogService._enriched(db, normalized)
