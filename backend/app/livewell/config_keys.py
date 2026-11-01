"""workflow_config keys for SafeHome 360™ / LiveWell360 tenant config (no service imports)."""

RUBRIC_KEY = "home_safety_rubric"
SOLUTIONS_KEY = "home_safety_solutions"
CATALOG_KEY = "home_safety_catalog"
PRICING_KEY = "home_safety_pricing"
SUPPLIERS_KEY = "home_safety_suppliers"
AI_CONFIG_KEY = "home_safety_ai"
RULE_ENGINE_KEY = "livewell_rule_engine"

# Spreadsheet sync metadata (not an entity payload)
MASTER_BASELINE_KEY = "home_safety_master_baseline"
MASTER_STAGING_KEY = "home_safety_master_staging"
MASTER_VERSIONS_KEY = "home_safety_master_versions"

CONFIG_KEYS = {
    "rubric": RUBRIC_KEY,
    "solutions": SOLUTIONS_KEY,
    "catalog": CATALOG_KEY,
    "pricing": PRICING_KEY,
    "suppliers": SUPPLIERS_KEY,
    "ai_config": AI_CONFIG_KEY,
    "rule_engine": RULE_ENGINE_KEY,
}
