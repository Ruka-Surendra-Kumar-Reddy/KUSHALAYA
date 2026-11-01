"""Pure-function coverage for scripts/rename_lwa_to_kaa (no DB access)."""

from app.livewell.catalog_defaults import DEFAULT_CATALOG
from app.livewell.config_keys import CATALOG_KEY, RUBRIC_KEY
from scripts.rename_lwa_to_kaa import ( brand_spelling,
    BRAND_TITLE_NEW,
    fix_catalog,
    fix_workflow_config,
    rename_in,
    reset_assessment_product,
)


def _factory_svc001() -> dict:
    return next(p for p in DEFAULT_CATALOG["products"] if p["product_code"] == "SVC-001")


def test_rename_in_replaces_brand_title_and_lwa_word_only():
    changes: list[str] = []
    value = {
        "SVC_LWA_x": "LiveWell360 Assessment (LWA) — LWA report; LWA_ID stays",
        "nested": ["LiveWell360 Assessment (KAA)", 3, None],
    }
    out = rename_in(value, "t", changes)
    assert out["SVC_LWA_x"] == "KushAlaya Assessment (KAA) — KAA report; LWA_ID stays"
    assert out["nested"] == [BRAND_TITLE_NEW, 3, None]
    assert list(out) == ["SVC_LWA_x", "nested"]  # keys untouched
    assert len(changes) == 2


def test_rename_in_can_skip_lwa_pass():
    changes: list[str] = []
    assert rename_in("LWA guide for LiveWell360 Assessment (LWA)", "t", changes, lwa=False) == (
        "LWA guide for KushAlaya Assessment (KAA)"
    )


def test_reset_assessment_product_only_when_still_livewell():
    factory = _factory_svc001()
    catalog = {
        "products": [
            {
                "id": "prod_svc_001",
                "product_code": "SVC-001",
                "name": "LiveWell Assessment",
                "short_description": "Custom copy without the old brand",
                "price_inr": 9999,
            },
            {"id": "other", "product_code": "BTH-001", "name": "LiveWell grab bar"},
        ]
    }
    changes: list[str] = []
    out = reset_assessment_product(catalog, "g", changes)
    svc = out["products"][0]
    assert svc["name"] == brand_spelling(factory["name"])
    assert svc["short_description"] == "Custom copy without the old brand"
    assert svc["price_inr"] == 9999  # only name/short_description are reset
    assert out["products"][1]["name"] == "LiveWell grab bar"  # other products untouched
    assert len(changes) == 1
    assert catalog["products"][0]["name"] == "LiveWell Assessment"  # input not mutated


def test_fix_catalog_is_idempotent():
    catalog = {
        "products": [
            {"id": "prod_svc_001", "product_code": "SVC-001", "name": "LiveWell360 Assessment (LWA)",
             "short_description": "On-site LWA visit"},
        ],
        "packages": [{"id": "p1", "name": "Essential", "description": "Includes the LWA"}],
    }
    first: list[str] = []
    once = fix_catalog(catalog, "g", first)
    assert once["products"][0]["name"] == brand_spelling(_factory_svc001()["name"])
    # No "LiveWell" in the short description, so it is not factory-reset — only LWA -> KAA.
    assert once["products"][0]["short_description"] == "On-site KAA visit"
    assert once["packages"][0]["description"] == "Includes the KAA"
    assert first

    second: list[str] = []
    assert fix_catalog(once, "g", second) == once
    assert second == []


def test_fix_workflow_config_scopes_lwa_pass_to_catalog():
    cfg = {
        CATALOG_KEY: {"products": [{"id": "x", "product_code": "BTH-001", "name": "LWA bar"}]},
        RUBRIC_KEY: {"title": "LiveWell360 Assessment (KAA)", "note": "LWA items"},
        "unrelated": 5,
    }
    changes: list[str] = []
    out = fix_workflow_config(cfg, "tenant[1]", changes)
    assert out[CATALOG_KEY]["products"][0]["name"] == "KAA bar"
    assert out[RUBRIC_KEY]["title"] == BRAND_TITLE_NEW
    assert out[RUBRIC_KEY]["note"] == "LWA items"  # bare LWA outside the catalog is left alone
    assert out["unrelated"] == 5
    assert len(changes) == 2
