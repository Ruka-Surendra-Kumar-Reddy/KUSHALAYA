#!/usr/bin/env python3
"""Verify workforceos-core is present and matches backend imports."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_CANDIDATES = (
    REPO_ROOT / "workforceos-core",
    REPO_ROOT.parent / "workforceos-core",
    Path("/opt/workforceos-core"),
)


def _core_root() -> Path | None:
    env = os.environ.get("WORKFORCEOS_CORE", "").strip()
    if env:
        candidate = Path(env)
        if (candidate / "contracts" / "verticals.json").is_file():
            return candidate
    for candidate in CORE_CANDIDATES:
        if (candidate / "contracts" / "verticals.json").is_file():
            return candidate
    return None


def main() -> int:
    core_root = _core_root()
    if core_root is None:
        print(
            "Missing workforceos-core checkout. Clone beside this repo or set WORKFORCEOS_CORE:\n"
            "  git clone -b develop https://github.com/krishnaposa/workforceos-core.git workforceos-core\n"
            "  export WORKFORCEOS_CORE=/opt/workforceos-core",
            file=sys.stderr,
        )
        return 1

    contract = core_root / "contracts" / "verticals.json"
    markets_contract = core_root / "contracts" / "markets.json"
    roles_contract = core_root / "contracts" / "roles.json"
    nav_contract = core_root / "contracts" / "nav.json"
    platform_en = core_root / "contracts" / "messages" / "platform.en.json"
    themes_contract = core_root / "contracts" / "themes.json"
    payload = json.loads(contract.read_text(encoding="utf-8"))
    markets_payload = json.loads(markets_contract.read_text(encoding="utf-8"))
    roles_payload = json.loads(roles_contract.read_text(encoding="utf-8"))
    nav_payload = json.loads(nav_contract.read_text(encoding="utf-8"))
    platform_payload = json.loads(platform_en.read_text(encoding="utf-8"))
    themes_payload = json.loads(themes_contract.read_text(encoding="utf-8"))
    try:
        from workforceos_core import verticals as core
        from workforceos_core import markets as core_markets
        from workforceos_core import rbac as core_rbac
    except ImportError as exc:
        print(f"Install workforceos-core: pip install -e workforceos-core/python ({exc})", file=sys.stderr)
        return 1

    if core.DEFAULT_VERTICAL != payload["defaultVertical"]:
        print("DEFAULT_VERTICAL drift", file=sys.stderr)
        return 1
    if set(core.VALID_VERTICALS) != set(payload["validVerticals"]):
        print("VALID_VERTICALS drift", file=sys.stderr)
        return 1
    if core.VERTICAL_LABELS != payload["verticalLabels"]:
        print("VERTICAL_LABELS drift", file=sys.stderr)
        return 1
    if core_markets.DEFAULT_MARKET != markets_payload["defaultMarket"]:
        print("DEFAULT_MARKET drift", file=sys.stderr)
        return 1
    if core_rbac.SYSTEM_ADMIN != roles_payload["systemAdmin"]:
        print("SYSTEM_ADMIN drift", file=sys.stderr)
        return 1
    if nav_payload.get("schemaVersion") != 1:
        print("nav.json schemaVersion drift", file=sys.stderr)
        return 1
    if not platform_payload.get("nav", {}).get("items"):
        print("platform.en.json nav drift", file=sys.stderr)
        return 1
    if themes_payload.get("defaultTheme") != "classic":
        print("themes.json defaultTheme drift", file=sys.stderr)
        return 1

    wf_events = core_root / "contracts" / "workflow_events.json"
    if not wf_events.is_file():
        print("missing workflow_events.json", file=sys.stderr)
        return 1

    db_packs = core_root / "contracts" / "database_packs.json"
    if not db_packs.is_file():
        print("missing database_packs.json", file=sys.stderr)
        return 1
    db_payload = json.loads(db_packs.read_text(encoding="utf-8"))
    try:
        from workforceos_core import database_packs as core_db_packs
    except ImportError as exc:
        print(f"database_packs import failed ({exc})", file=sys.stderr)
        return 1
    if set(core_db_packs.SHARED_PACKS) != set(db_payload["sharedPacks"]):
        print("SHARED_PACKS drift", file=sys.stderr)
        return 1

    print("workforceos-core contract OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
