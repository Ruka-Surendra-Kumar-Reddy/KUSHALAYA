"""Field-level drift between last approved spreadsheet baseline and live DB config."""

from __future__ import annotations

import json
from typing import Any

from app.livewell.config_keys import CONFIG_KEYS
from app.livewell.stored_config import entity_is_empty, normalize_entity_config

MAX_FIELD_CHANGES = 250

PRODUCT_WATCH = (
    "name",
    "product_code",
    "category",
    "category_prefix",
    "short_description",
    "details",
    "price_inr",
    "price_label",
    "contractor_type",
    "install_time",
    "safety_improvement",
    "solution_ids",
)
PACKAGE_WATCH = (
    "name",
    "tagline",
    "description",
    "price_inr",
    "price_label",
    "highlight",
    "product_ids",
    "sort_order",
)
SOLUTION_WATCH = (
    "name",
    "finding",
    "section",
    "subcategory",
    "priority",
    "riskDescription",
    "estimatedCost",
    "contractorType",
    "scoreImprovement",
    "rubricItemIds",
    "membershipImpact",
    "evidenceLevel",
)
SUPPLIER_WATCH = ("name", "contact", "phone", "email", "city", "rating", "active")
OFFER_WATCH = (
    "supplier_cost_inr",
    "preferred",
    "moq",
    "lead_time_days",
    "vendor_sku",
    "active",
)


def _canon(value: Any) -> Any:
    if isinstance(value, list):
        if value and all(isinstance(x, str) for x in value):
            return sorted(value)
        return [_canon(x) for x in value]
    if isinstance(value, dict):
        return {k: _canon(value[k]) for k in sorted(value.keys())}
    return value


def _vals_equal(a: Any, b: Any) -> bool:
    return json.dumps(_canon(a), sort_keys=True, default=str) == json.dumps(
        _canon(b), sort_keys=True, default=str
    )


def _append(
    changes: list[dict],
    *,
    entity: str,
    record_id: str,
    field: str,
    before: Any,
    after: Any,
    change_type: str = "changed",
) -> None:
    if len(changes) >= MAX_FIELD_CHANGES:
        return
    changes.append(
        {
            "entity": entity,
            "id": record_id,
            "field": field,
            "before": before,
            "after": after,
            "change_type": change_type,
        }
    )


def _diff_records(
    changes: list[dict],
    *,
    entity: str,
    old_by_id: dict[str, dict],
    new_by_id: dict[str, dict],
    watch: tuple[str, ...],
) -> None:
    old_ids = set(old_by_id)
    new_ids = set(new_by_id)
    for rid in sorted(new_ids - old_ids):
        _append(
            changes,
            entity=entity,
            record_id=rid,
            field="*",
            before=None,
            after=new_by_id[rid].get("name") or rid,
            change_type="added",
        )
    for rid in sorted(old_ids - new_ids):
        _append(
            changes,
            entity=entity,
            record_id=rid,
            field="*",
            before=old_by_id[rid].get("name") or rid,
            after=None,
            change_type="removed",
        )
    for rid in sorted(old_ids & new_ids):
        o = old_by_id[rid]
        n = new_by_id[rid]
        for field in watch:
            ov = o.get(field)
            nv = n.get(field)
            if not _vals_equal(ov, nv):
                _append(
                    changes,
                    entity=entity,
                    record_id=rid,
                    field=field,
                    before=ov,
                    after=nv,
                )


def compute_field_drift(baseline: dict | None, current: dict | None) -> dict:
    """Compare approved spreadsheet baseline to live config; return field-level changes."""
    base = normalize_entity_config(baseline)
    live = normalize_entity_config(current)
    changes: list[dict] = []

    # Rubric categories / questions
    old_cats = {c["id"]: c for c in (base.get("rubric") or {}).get("categories") or [] if c.get("id")}
    new_cats = {c["id"]: c for c in (live.get("rubric") or {}).get("categories") or [] if c.get("id")}
    _diff_records(
        changes,
        entity="rubric_category",
        old_by_id=old_cats,
        new_by_id=new_cats,
        watch=("title", "maxPoints", "sectionNumber"),
    )
    old_q: dict[str, dict] = {}
    new_q: dict[str, dict] = {}
    for c in old_cats.values():
        for item in c.get("items") or []:
            if item.get("id"):
                old_q[item["id"]] = {**item, "category_id": c["id"]}
    for c in new_cats.values():
        for item in c.get("items") or []:
            if item.get("id"):
                new_q[item["id"]] = {**item, "category_id": c["id"]}
    _diff_records(
        changes,
        entity="rubric_question",
        old_by_id=old_q,
        new_by_id=new_q,
        watch=("label", "maxPoints", "group", "scoringScale", "source", "category_id"),
    )

    old_sol = {
        s["id"]: s for s in (base.get("solutions") or {}).get("solutions") or [] if s.get("id")
    }
    new_sol = {
        s["id"]: s for s in (live.get("solutions") or {}).get("solutions") or [] if s.get("id")
    }
    _diff_records(
        changes,
        entity="solution",
        old_by_id=old_sol,
        new_by_id=new_sol,
        watch=SOLUTION_WATCH,
    )

    old_prod = {
        p["id"]: p for p in (base.get("catalog") or {}).get("products") or [] if p.get("id")
    }
    new_prod = {
        p["id"]: p for p in (live.get("catalog") or {}).get("products") or [] if p.get("id")
    }
    _diff_records(
        changes,
        entity="product",
        old_by_id=old_prod,
        new_by_id=new_prod,
        watch=PRODUCT_WATCH,
    )

    old_pkg = {
        p["id"]: p for p in (base.get("catalog") or {}).get("packages") or [] if p.get("id")
    }
    new_pkg = {
        p["id"]: p for p in (live.get("catalog") or {}).get("packages") or [] if p.get("id")
    }
    _diff_records(
        changes,
        entity="package",
        old_by_id=old_pkg,
        new_by_id=new_pkg,
        watch=PACKAGE_WATCH,
    )

    old_pricing = base.get("pricing") or {}
    new_pricing = live.get("pricing") or {}
    for key in sorted(set(old_pricing) | set(new_pricing)):
        if not _vals_equal(old_pricing.get(key), new_pricing.get(key)):
            _append(
                changes,
                entity="pricing",
                record_id="pricing",
                field=key,
                before=old_pricing.get(key),
                after=new_pricing.get(key),
                change_type="changed"
                if key in old_pricing and key in new_pricing
                else ("added" if key in new_pricing else "removed"),
            )

    old_sup = {
        s["id"]: s for s in (base.get("suppliers") or {}).get("suppliers") or [] if s.get("id")
    }
    new_sup = {
        s["id"]: s for s in (live.get("suppliers") or {}).get("suppliers") or [] if s.get("id")
    }
    _diff_records(
        changes,
        entity="supplier",
        old_by_id=old_sup,
        new_by_id=new_sup,
        watch=SUPPLIER_WATCH,
    )

    def offer_key(o: dict) -> str:
        return f"{o.get('product_id')}::{o.get('supplier_id')}"

    old_off = {
        offer_key(o): o
        for o in (base.get("suppliers") or {}).get("offers") or []
        if o.get("product_id") and o.get("supplier_id")
    }
    new_off = {
        offer_key(o): o
        for o in (live.get("suppliers") or {}).get("offers") or []
        if o.get("product_id") and o.get("supplier_id")
    }
    _diff_records(
        changes,
        entity="supplier_offer",
        old_by_id=old_off,
        new_by_id=new_off,
        watch=OFFER_WATCH,
    )

    # AI + rule_engine: summary-level (structure heavy)
    for entity in ("ai_config", "rule_engine"):
        if not _vals_equal(base.get(entity), live.get(entity)):
            _append(
                changes,
                entity=entity,
                record_id=entity,
                field="*",
                before="(baseline)",
                after="(changed)",
                change_type="changed",
            )

    truncated = len(changes) >= MAX_FIELD_CHANGES and True
    # Recompute exact count if truncated — approximate by continuing without storing
    full_count = len(changes)
    if truncated:
        # Signal UI that more exist; we capped storage
        pass

    by_entity: dict[str, int] = {}
    for ch in changes:
        by_entity[ch["entity"]] = by_entity.get(ch["entity"], 0) + 1

    return {
        "dirty": full_count > 0,
        "change_count": full_count,
        "truncated": truncated,
        "by_entity": by_entity,
        "changes": changes,
    }


def config_is_effectively_empty(config: dict | None) -> bool:
    cfg = normalize_entity_config(config)
    return all(entity_is_empty(entity, cfg.get(entity) or {}) for entity in CONFIG_KEYS)
