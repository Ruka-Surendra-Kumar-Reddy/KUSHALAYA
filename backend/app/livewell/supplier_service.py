"""SafeHome 360™ supplier directory — per-tenant workflow_config storage."""

from __future__ import annotations

from copy import deepcopy

from sqlalchemy.orm import Session

from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request
from app.livewell.config_keys import CATALOG_KEY, SUPPLIERS_KEY
from app.livewell.stored_config import read_stored_config
from app.livewell.supplier_defaults import DEFAULT_SUPPLIERS
from app.models.tenant import Tenant
from app.models.user import User


def _offer_id(product_id: str, supplier_id: str) -> str:
    return f"offer_{product_id}_{supplier_id}"


def _normalize_roles(raw) -> list[str]:
    roles: list[str] = []
    if isinstance(raw, str):
        parts = [p.strip().lower() for p in raw.replace("|", ",").split(",")]
    elif isinstance(raw, list):
        parts = [str(p).strip().lower() for p in raw]
    else:
        parts = []
    for role in parts:
        if role in ("supplier", "installer") and role not in roles:
            roles.append(role)
    return roles or ["supplier"]


def _normalize_supplier(raw: dict, index: int = 0) -> dict:
    rating = raw.get("rating")
    parsed_rating = None
    if rating is not None and rating != "":
        try:
            # Stored to one decimal — the UI shows one, so 4.33 and 4.3 must not
            # look equal while comparing unequal.
            parsed_rating = round(max(0.0, min(5.0, float(rating))), 1)
        except (TypeError, ValueError):
            parsed_rating = None

    rolling = raw.get("rolling_rating")
    parsed_rolling = None
    if rolling is not None and rolling != "":
        try:
            parsed_rolling = round(max(0.0, min(5.0, float(rolling))), 1)
        except (TypeError, ValueError):
            parsed_rolling = None

    try:
        rolling_count = max(0, int(raw.get("rolling_rating_count") or 0))
    except (TypeError, ValueError):
        rolling_count = 0
    try:
        rolling_window = max(1, min(20, int(raw.get("rolling_window") or 5)))
    except (TypeError, ValueError):
        rolling_window = 5

    tier = str(raw.get("partner_tier", "")).strip().lower()
    if tier not in ("", "founding_platinum", "gold", "silver"):
        tier = ""

    return {
        "id": str(raw.get("id", "")).strip(),
        "name": str(raw.get("name", "")).strip(),
        "contact": str(raw.get("contact", "")).strip(),
        "phone": str(raw.get("phone", "")).strip(),
        "email": str(raw.get("email", "")).strip(),
        "city": str(raw.get("city", "")).strip(),
        "rating": parsed_rating,
        "roles": _normalize_roles(raw.get("roles")),
        "category": str(raw.get("category", "")).strip(),
        "partner_tier": tier,
        "rolling_rating": parsed_rolling,
        "rolling_rating_count": rolling_count,
        "rolling_window": rolling_window,
        "active": bool(raw.get("active", True)),
        "sort_order": int(raw.get("sort_order", index)),
    }


def _normalize_offer(raw: dict, valid_supplier_ids: set[str]) -> dict | None:
    product_id = str(raw.get("product_id", "")).strip()
    supplier_id = str(raw.get("supplier_id", "")).strip()
    if not product_id or not supplier_id:
        return None
    if supplier_id not in valid_supplier_ids:
        return None
    offer_id = str(raw.get("id", "")).strip() or _offer_id(product_id, supplier_id)
    try:
        cost = max(0, int(raw.get("supplier_cost_inr") or 0))
    except (TypeError, ValueError):
        cost = 0
    try:
        moq = max(1, int(raw.get("moq") or 1))
    except (TypeError, ValueError):
        moq = 1
    try:
        lead = max(0, int(raw.get("lead_time_days") or 0))
    except (TypeError, ValueError):
        lead = 0
    return {
        "id": offer_id,
        "product_id": product_id,
        "supplier_id": supplier_id,
        "supplier_cost_inr": cost,
        "preferred": bool(raw.get("preferred", False)),
        "moq": moq,
        "lead_time_days": lead,
        "vendor_sku": str(raw.get("vendor_sku", "")).strip(),
        "active": bool(raw.get("active", True)),
    }


def _resolve_preferred_offers(offers: list[dict]) -> list[dict]:
    """Ensure at most one preferred offer per product."""
    by_product: dict[str, list[dict]] = {}
    for offer in offers:
        by_product.setdefault(offer["product_id"], []).append(offer)

    resolved: list[dict] = []
    for product_offers in by_product.values():
        preferred = [o for o in product_offers if o.get("preferred")]
        if len(preferred) > 1:
            keep = min(preferred, key=lambda o: (o.get("supplier_cost_inr", 0), o.get("id", "")))
            for offer in product_offers:
                resolved.append(
                    {
                        **offer,
                        "preferred": offer["id"] == keep["id"],
                    }
                )
        else:
            resolved.extend(product_offers)
    return sorted(resolved, key=lambda o: (o["product_id"], o["supplier_id"]))


def normalize_supplier_directory(
    raw: dict,
    *,
    valid_product_ids: set[str] | None = None,
) -> dict:
    suppliers = [
        s
        for i, item in enumerate(raw.get("suppliers") or [])
        if (s := _normalize_supplier(item, i)).get("id") and s.get("name")
    ]
    suppliers.sort(key=lambda s: (s.get("sort_order", 0), s.get("name", "")))
    supplier_ids = {s["id"] for s in suppliers}

    offers: list[dict] = []
    seen_pairs: set[tuple[str, str]] = set()
    for item in raw.get("offers") or []:
        offer = _normalize_offer(item, supplier_ids)
        if not offer:
            continue
        pair = (offer["product_id"], offer["supplier_id"])
        if pair in seen_pairs:
            continue
        if valid_product_ids is not None and offer["product_id"] not in valid_product_ids:
            continue
        seen_pairs.add(pair)
        offers.append(offer)

    offers = _resolve_preferred_offers(offers)
    return {"suppliers": suppliers, "offers": offers}


class HomeSafetySupplierService:

    @staticmethod
    def _tenant(db: Session, user: User) -> Tenant:
        tid = resolve_tenant_id(user)
        if tid is None:
            raise_bad_request("Tenant required")
        tenant = db.query(Tenant).filter(Tenant.id == tid).first()
        if not tenant:
            raise_bad_request("Tenant not found")
        assert_tenant_access(user, tenant.id)
        return tenant

    @staticmethod
    def _product_ids_from_tenant(tenant: Tenant) -> set[str]:
        cfg = tenant.workflow_config or {}
        catalog = cfg.get(CATALOG_KEY)
        if not isinstance(catalog, dict):
            return set()
        return {
            str(p["id"])
            for p in (catalog.get("products") or [])
            if isinstance(p, dict) and p.get("id")
        }

    @staticmethod
    def get_suppliers(db: Session, user: User) -> dict:
        tenant = HomeSafetySupplierService._tenant(db, user)
        stored = read_stored_config(tenant.workflow_config or {})["suppliers"]
        if not stored or not (stored.get("suppliers") or stored.get("offers")):
            stored = DEFAULT_SUPPLIERS
        product_ids = HomeSafetySupplierService._product_ids_from_tenant(tenant)
        return normalize_supplier_directory(
            stored,
            valid_product_ids=product_ids or None,
        )

    @staticmethod
    def save_suppliers(db: Session, user: User, payload: dict) -> dict:
        tenant = HomeSafetySupplierService._tenant(db, user)
        product_ids = HomeSafetySupplierService._product_ids_from_tenant(tenant)
        normalized = normalize_supplier_directory(payload, valid_product_ids=product_ids or None)

        orphan_offers = [
            o
            for o in (payload.get("offers") or [])
            if str(o.get("product_id", "")).strip()
            and product_ids
            and str(o.get("product_id", "")).strip() not in product_ids
        ]
        if orphan_offers:
            raise_bad_request(
                "Some product offers reference unknown product IDs — load the catalog first."
            )

        cfg = dict(tenant.workflow_config or {})
        cfg[SUPPLIERS_KEY] = normalized
        tenant.workflow_config = cfg
        db.commit()
        db.refresh(tenant)
        return normalized
