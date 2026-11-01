"""Rolling partner ratings from family visit experience scores."""

from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.livewell.config_keys import SUPPLIERS_KEY
from app.livewell.supplier_service import normalize_supplier_directory
from app.livewell.visit_service import _parse_dt, normalize_visit
from app.models.elder import Elder
from app.models.tenant import Tenant

DEFAULT_WINDOW = 5
MIN_PUBLIC_COUNT = 3


def collect_partner_experience_ratings(db: Session, tenant_id: int, partner_id: str) -> list[dict]:
    """All experience ratings for a partner, newest visit first."""
    elders = db.query(Elder).filter(Elder.tenant_id == tenant_id).all()
    rows: list[dict] = []
    for elder in elders:
        attrs = elder.custom_attributes or {}
        block = attrs.get("safe_home")
        if not isinstance(block, dict):
            continue
        for raw in block.get("visits") or []:
            if not isinstance(raw, dict):
                continue
            visit = normalize_visit(raw)
            if visit.get("partner_id") != partner_id:
                continue
            rating = visit.get("experience_rating")
            if rating is None:
                continue
            rows.append(
                {
                    "visit_id": visit["id"],
                    "elder_id": elder.id,
                    "visited_at": visit["visited_at"],
                    "rating": int(rating),
                    "comment": visit.get("experience_comment") or "",
                    "visit_type": visit.get("visit_type") or "",
                }
            )
    rows.sort(key=lambda r: r["visited_at"], reverse=True)
    return rows


def recompute_partner_rolling_rating(db: Session, tenant_id: int, partner_id: str) -> dict | None:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return None

    cfg = dict(tenant.workflow_config or {})
    directory = normalize_supplier_directory(cfg.get(SUPPLIERS_KEY) or {})
    suppliers = directory.get("suppliers") or []
    target = None
    for s in suppliers:
        if s.get("id") == partner_id:
            target = s
            break
    if not target:
        return None

    window = int(target.get("rolling_window") or DEFAULT_WINDOW)
    window = max(1, min(20, window))
    ratings = collect_partner_experience_ratings(db, tenant_id, partner_id)
    sample = ratings[:window]
    if sample:
        # One decimal, matching the seed rating and every UI display.
        avg = round(sum(r["rating"] for r in sample) / len(sample), 1)
        target["rolling_rating"] = avg
        target["rolling_rating_count"] = len(sample)
    else:
        target["rolling_rating"] = None
        target["rolling_rating_count"] = 0
    target["rolling_window"] = window

    directory["suppliers"] = suppliers
    cfg[SUPPLIERS_KEY] = directory
    tenant.workflow_config = cfg
    flag_modified(tenant, "workflow_config")
    db.commit()
    db.refresh(tenant)
    return target


def display_partner_rating(supplier: dict) -> float | None:
    """Prefer rolling rating once enough reviews exist; else manual seed."""
    count = int(supplier.get("rolling_rating_count") or 0)
    rolling = supplier.get("rolling_rating")
    if count >= MIN_PUBLIC_COUNT and rolling is not None:
        return float(rolling)
    seed = supplier.get("rating")
    if seed is not None:
        return float(seed)
    if rolling is not None and count > 0:
        return float(rolling)
    return None
