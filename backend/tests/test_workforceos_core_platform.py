"""Ensure backend platform shims match workforceos-core."""

import json
from pathlib import Path

from workforceos_core import markets as core_markets
from workforceos_core import rbac as core_rbac
from workforceos_core import verticals as core_verticals


def _contract_root() -> Path:
    return Path(core_verticals.__file__).resolve().parents[3] / "contracts"


def test_markets_reexport():
    from app.core import markets as app_markets

    payload = json.loads((_contract_root() / "markets.json").read_text(encoding="utf-8"))
    assert app_markets.DEFAULT_MARKET == payload["defaultMarket"]
    assert app_markets.normalize_market(None, country="India") == core_markets.normalize_market(
        None, country="India"
    )


def test_rbac_reexport():
    from app.core import rbac as app_rbac

    payload = json.loads((_contract_root() / "roles.json").read_text(encoding="utf-8"))
    assert app_rbac.SYSTEM_ADMIN == payload["systemAdmin"]
    assert app_rbac.CAREGIVER == core_rbac.CAREGIVER


def test_security_shim_configured():
    from app.core.security import create_access_token, decode_token

    token = create_access_token("phase3@test.com", role="TENANT_ADMIN", tenant_id=1)
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "phase3@test.com"
