"""Assessment finding -> product links (docs/ASSESSMENT_PRODUCT_LINKS.md) and the live-catalog fix."""

from copy import deepcopy

from app.livewell.catalog_defaults import DEFAULT_CATALOG
from app.livewell.catalog_link_fixes import (
    LINK_FIXES,
    LINK_FIXES_KEY,
    LINK_FIXES_VERSION,
    V3_PRODUCT_LINKS,
    apply_link_fixes,
    apply_link_fixes_once,
    apply_v3_additions,
)
from app.livewell.commerce import catalog_products
from app.livewell.global_catalog_store import (
    ensure_global_catalog_dict,
    load_raw_global_catalog,
    save_raw_global_catalog,
)
from app.models.app_global_setting import AppGlobalSetting


def _for(catalog: dict, solution_id: str) -> set[str]:
    return {p["product_code"] for p in catalog["products"] if solution_id in (p.get("solution_ids") or [])}


def _check_findings(catalog: dict) -> None:
    stairs = _for(catalog, "LW-HS-STA-001")
    assert stairs == {"EXT-001", "BTH-009"}
    wander = _for(catalog, "LW-COG-WAN-001")
    assert wander == {"SMT-005", "SMT-004", "SMT-012", "SMT-006"}
    assert _for(catalog, "LW-EMG-COM-001") == {"SVC-005", "EMG-001", "SMT-011", "EMG-006", "SMT-006"}
    assert "BTH-009" in _for(catalog, "LW-HS-BTH-002")
    # no kitchen items on stairs, no water-leak / hallway lights for wandering
    assert not any(c.startswith("KIT-") for c in stairs)
    assert not {"SMT-009", "HAL-001"} & wander
    # v3: shop-only products now in the assessment catalog and linked
    assert "BTH-013" in _for(catalog, "LW-HS-BTH-010")
    assert "BTH-012" in _for(catalog, "LW-HS-BTH-002") and "BTH-012" in _for(catalog, "LW-HS-BTH-003")
    assert {"HLT-001", "HLT-002", "HLT-003"} <= _for(catalog, "LW-HL-MON-001")
    assert "HLT-004" in _for(catalog, "LW-HL-MED-001")


def test_seed_catalog_links():
    _check_findings(DEFAULT_CATALOG)


def test_link_fixes_match_seed_and_known_solutions():
    import json
    from pathlib import Path

    seed = {p["product_code"]: p["solution_ids"] for p in DEFAULT_CATALOG["products"]}
    for code, ids in LINK_FIXES.items():
        assert seed[code] == ids, code
    sols = json.loads(
        (Path(__file__).resolve().parents[1] / "app/livewell/default_solutions.json").read_text(encoding="utf-8")
    )["solutions"]
    known = {s["id"] for s in sols}
    for ids in seed.values():
        assert set(ids) <= known


def test_new_products_not_duplicated_in_commerce():
    codes = [p["product_code"] for p in catalog_products()]
    assert codes.count("EMG-006") == 1 and codes.count("SMT-012") == 1
    for code in V3_PRODUCT_LINKS:
        assert codes.count(code) == 1, code
    assert len(codes) == len(set(codes))


def _old_live_catalog() -> dict:
    """A live catalog as seeded before the fix: old wrong links, no EMG-006/SMT-012, admin price edit."""
    cat = deepcopy(DEFAULT_CATALOG)
    gone = ("EMG-006", "SMT-012", *V3_PRODUCT_LINKS)
    cat["products"] = [p for p in cat["products"] if p["product_code"] not in gone]
    for p in cat["products"]:
        if p["product_code"] in ("KIT-001", "KIT-002"):
            p["solution_ids"] = ["LW-HS-STA-001"]
        if p["product_code"] == "SMT-009":
            p["solution_ids"] = ["LW-TECH-FAL-001"]
        if p["product_code"] == "EXT-001":
            p["price_inr"] = 12345
            p["solution_ids"] = ["LW-HS-ENT-002", "LW-HS-STA-001"]
    return cat


def test_apply_link_fixes_is_idempotent_and_only_touches_links():
    fixed, changes = apply_link_fixes(_old_live_catalog())
    fixed, more = apply_v3_additions(fixed)
    changes += more
    assert changes
    _check_findings(fixed)
    ext = next(p for p in fixed["products"] if p["product_code"] == "EXT-001")
    assert ext["price_inr"] == 12345 and ext["solution_ids"] == ["LW-HS-ENT-002", "LW-HS-STA-001"]
    again, changes2 = apply_link_fixes(fixed)
    assert changes2 == [] and again == fixed
    again, changes3 = apply_v3_additions(fixed)
    assert changes3 == [] and again == fixed


def test_loader_applies_fix_once_to_live_catalog(db):
    save_raw_global_catalog(db, _old_live_catalog())
    _check_findings(ensure_global_catalog_dict(db))
    _check_findings(load_raw_global_catalog(db))
    marker = db.get(AppGlobalSetting, LINK_FIXES_KEY)
    assert marker.value["version"] == LINK_FIXES_VERSION and marker.value["changes"] > 0

    # Later admin edits are kept: the fix does not run again.
    cat = load_raw_global_catalog(db)
    for p in cat["products"]:
        if p["product_code"] == "KIT-001":
            p["solution_ids"] = ["LW-HS-KIT-001"]
    save_raw_global_catalog(db, cat)
    reloaded = ensure_global_catalog_dict(db)
    kit = next(p for p in reloaded["products"] if p["product_code"] == "KIT-001")
    assert kit["solution_ids"] == ["LW-HS-KIT-001"]


def test_v3_only_adds_on_a_v2_catalog_and_keeps_admin_edits(db):
    """A live catalog already at v2: v3 adds the new products / HLT type, rewrites nothing else."""
    cat = _old_live_catalog()
    cat["category_types"] = [{"prefix": "BTH", "label": "Bathroom Safety", "kind": "product", "sort": 1}]
    seed_fan = next(p for p in DEFAULT_CATALOG["products"] if p["product_code"] == "BTH-013")
    fan = deepcopy(seed_fan)
    fan["price_inr"] = 4200  # admin price edit on an already-present product
    fan["solution_ids"] = ["LW-HS-BTH-004"]  # admin link
    cat["products"].append(fan)
    db.add(AppGlobalSetting(key=LINK_FIXES_KEY, value={"version": 2}))
    db.commit()

    fixed = apply_link_fixes_once(db, cat)
    by_code = {p["product_code"]: p for p in fixed["products"]}
    # v1/v2 rewrites are not re-run (KIT-001 keeps the stale admin-era link)
    assert by_code["KIT-001"]["solution_ids"] == ["LW-HS-STA-001"]
    assert by_code["BTH-013"]["price_inr"] == 4200
    assert by_code["BTH-013"]["solution_ids"] == ["LW-HS-BTH-004", "LW-HS-BTH-010"]
    for code, links in V3_PRODUCT_LINKS.items():
        assert set(links) <= set(by_code[code]["solution_ids"]), code
    codes = [p["product_code"] for p in fixed["products"]]
    assert len(codes) == len(set(codes))
    assert [t["prefix"] for t in fixed["category_types"]] == ["BTH", "HLT"]
    assert db.get(AppGlobalSetting, LINK_FIXES_KEY).value["version"] == LINK_FIXES_VERSION == 3
    # runs once
    assert apply_link_fixes_once(db, cat) is cat


def test_admin_write_before_first_load_is_never_overwritten(db):
    """Workbook import / admin save marks the fix done, so a later load leaves it alone."""
    from app.livewell.catalog_link_fixes import mark_link_fixes_current

    mark_link_fixes_current(db, "workbook import test")
    save_raw_global_catalog(db, _old_live_catalog())
    loaded = ensure_global_catalog_dict(db)
    kit = next(p for p in loaded["products"] if p["product_code"] == "KIT-001")
    assert kit["solution_ids"] == ["LW-HS-STA-001"]
    assert "BTH-013" not in {p["product_code"] for p in loaded["products"]}
    marker = db.get(AppGlobalSetting, LINK_FIXES_KEY).value
    assert marker["version"] == LINK_FIXES_VERSION and marker["superseded_by"] == "workbook import test"
