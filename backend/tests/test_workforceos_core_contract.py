"""Ensure backend re-exports match workforceos-core contract."""

import json
from pathlib import Path

from workforceos_core import verticals as core


def _contract_path() -> Path:
    return Path(core.__file__).resolve().parents[3] / "contracts" / "verticals.json"


def test_installed_contract_matches_python_module():
    payload = json.loads(_contract_path().read_text(encoding="utf-8"))
    assert core.DEFAULT_VERTICAL == payload["defaultVertical"]
    assert set(core.VALID_VERTICALS) == set(payload["validVerticals"])
    assert core.VERTICAL_LABELS == payload["verticalLabels"]


def test_elder_care_pack_from_core():
    assert core.has_feature("ELDER_CARE", "care_plans")
    assert core.has_feature("ELDER_CARE", "customer_portal_billing")
    assert not core.has_feature("HOUSEKEEPING", "elders")


def test_app_reexport_constants():
    from app.core import verticals as app_verticals

    assert app_verticals.ELDER_CARE == "ELDER_CARE"
    assert app_verticals.has_feature("HOUSEKEEPING", "cleaning_dispatch")
    assert app_verticals.normalize_vertical(None) == core.DEFAULT_VERTICAL
