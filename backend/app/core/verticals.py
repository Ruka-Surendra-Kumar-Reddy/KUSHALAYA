"""Re-export WorkforceOS vertical contract from workforceos-core.

Do not duplicate feature packs here — edit contracts/verticals.json in
https://github.com/krishnaposa/workforceos-core
"""

from workforceos_core.verticals import (
    DEFAULT_VERTICAL,
    VALID_VERTICALS,
    VERTICAL_FEATURES,
    VERTICAL_LABELS,
    WORKFORCE_CORE_FEATURES,
    has_feature,
    normalize_vertical,
    vertical_features,
    vertical_label,
)

# Back-compat constants referenced across vertical adapters and services.
ELDER_CARE = "ELDER_CARE"
SECURITY = "SECURITY"
HOUSEKEEPING = "HOUSEKEEPING"
DRIVER_SERVICES = "DRIVER_SERVICES"
HOME_HEALTHCARE = "HOME_HEALTHCARE"
LIVEWELL360 = "LIVEWELL360"

__all__ = [
    "DEFAULT_VERTICAL",
    "VALID_VERTICALS",
    "VERTICAL_FEATURES",
    "VERTICAL_LABELS",
    "WORKFORCE_CORE_FEATURES",
    "ELDER_CARE",
    "SECURITY",
    "HOUSEKEEPING",
    "DRIVER_SERVICES",
    "HOME_HEALTHCARE",
    "LIVEWELL360",
    "has_feature",
    "normalize_vertical",
    "vertical_features",
    "vertical_label",
]
