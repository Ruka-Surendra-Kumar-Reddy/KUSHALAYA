"""Tenant workflow_config keys for SafeHome 360™ — SSOT for ElderCareOps + SafeHomeOps."""

from __future__ import annotations

RUBRIC_KEY = "home_safety_rubric"
SOLUTIONS_KEY = "home_safety_solutions"
CATALOG_KEY = "home_safety_catalog"
PRICING_KEY = "home_safety_pricing"
SUPPLIERS_KEY = "home_safety_suppliers"
AI_CONFIG_KEY = "home_safety_ai"
RULE_ENGINE_KEY = "livewell_rule_engine"
STAGING_KEY = "home_safety_master_staging"
VERSIONS_KEY = "home_safety_master_versions"

CONFIG_KEYS: dict[str, str] = {
    "rubric": RUBRIC_KEY,
    "solutions": SOLUTIONS_KEY,
    "catalog": CATALOG_KEY,
    "pricing": PRICING_KEY,
    "suppliers": SUPPLIERS_KEY,
    "ai_config": AI_CONFIG_KEY,
    "rule_engine": RULE_ENGINE_KEY,
}
