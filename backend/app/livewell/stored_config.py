"""Read SafeHome 360™ config persisted in tenant.workflow_config (single source of truth)."""

from __future__ import annotations

from typing import Any

from app.livewell.config_keys import (
    AI_CONFIG_KEY,
    CATALOG_KEY,
    CONFIG_KEYS,
    PRICING_KEY,
    RUBRIC_KEY,
    RULE_ENGINE_KEY,
    SOLUTIONS_KEY,
    SUPPLIERS_KEY,
)

EMPTY_BY_ENTITY: dict[str, Any] = {
    "rubric": {"categories": []},
    "solutions": {"solutions": []},
    "catalog": {"products": [], "packages": []},
    "pricing": {},
    "suppliers": {"suppliers": [], "offers": []},
    "ai_config": {},
    "rule_engine": {},
}


def read_stored_config(cfg: dict | None) -> dict:
    """Return only what is saved in workflow_config — no file defaults."""
    raw = cfg or {}
    return {
        "rubric": raw[RUBRIC_KEY] if isinstance(raw.get(RUBRIC_KEY), dict) else {"categories": []},
        "solutions": raw[SOLUTIONS_KEY] if isinstance(raw.get(SOLUTIONS_KEY), dict) else {"solutions": []},
        "catalog": raw[CATALOG_KEY] if isinstance(raw.get(CATALOG_KEY), dict) else {"products": [], "packages": []},
        "pricing": raw[PRICING_KEY] if isinstance(raw.get(PRICING_KEY), dict) else {},
        "suppliers": raw[SUPPLIERS_KEY] if isinstance(raw.get(SUPPLIERS_KEY), dict) else {"suppliers": [], "offers": []},
        "ai_config": raw[AI_CONFIG_KEY] if isinstance(raw.get(AI_CONFIG_KEY), dict) else {},
        "rule_engine": raw[RULE_ENGINE_KEY] if isinstance(raw.get(RULE_ENGINE_KEY), dict) else {},
    }


def normalize_entity_config(data: dict | None) -> dict:
    """Entity-keyed config for deep compare — workflow_config or approve-time snapshot."""
    raw = data or {}
    if any(isinstance(raw.get(k), dict) for k in CONFIG_KEYS.values()):
        return read_stored_config(raw)
    return {
        entity: raw[entity] if isinstance(raw.get(entity), dict) else EMPTY_BY_ENTITY[entity]
        for entity in CONFIG_KEYS
    }


def entity_is_empty(entity: str, data: dict) -> bool:
    if entity == "rubric":
        return not data.get("categories")
    if entity == "solutions":
        return not data.get("solutions")
    if entity == "catalog":
        return not data.get("products") and not data.get("packages")
    if entity == "pricing":
        return not data
    if entity == "suppliers":
        return not data.get("suppliers") and not data.get("offers")
    if entity == "ai_config":
        from app.livewell.ai_config_service import ai_config_is_empty

        return ai_config_is_empty(data)
    if entity == "rule_engine":
        return not any(
            data.get(k)
            for k in (
                "membership_rules",
                "ecm_rules",
                "assessment_findings",
                "risk_rules",
                "quote_rules",
                "notification_rules",
                "followup_rules",
                "rule_master",
            )
        )
    return True
