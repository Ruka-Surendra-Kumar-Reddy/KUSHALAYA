"""Tests for stored config and seed service."""

from app.livewell.seed_service import seed_missing_defaults
from app.livewell.stored_config import read_stored_config


def test_read_stored_config_empty():
    cfg = read_stored_config({})
    assert cfg["rubric"]["categories"] == []
    assert cfg["solutions"]["solutions"] == []


def test_seed_missing_defaults_fills_rubric():
    from app.livewell.seed_service import CANONICAL_MASTER_WORKBOOK

    assert CANONICAL_MASTER_WORKBOOK.is_file(), "Run backend/scripts/build_master_workbook.py"
    cfg, seeded = seed_missing_defaults({}, only=("rubric",))
    assert "rubric" in seeded
    stored = read_stored_config(cfg)
    assert len(stored["rubric"]["categories"]) > 0


def test_seed_tenant_defaults_stamps_baseline(db, seed_tenant):
    from sqlalchemy.orm.attributes import flag_modified

    from app.livewell.config_keys import MASTER_BASELINE_KEY
    from app.livewell.seed_service import seed_tenant_defaults

    tenant = seed_tenant["tenant"]
    tenant.workflow_config = {}
    flag_modified(tenant, "workflow_config")
    db.commit()
    db.refresh(tenant)

    seeded = seed_tenant_defaults(db, tenant)
    db.refresh(tenant)
    assert seeded
    assert any(s.startswith("baseline:md-seed-") for s in seeded)
    baseline = (tenant.workflow_config or {}).get(MASTER_BASELINE_KEY) or {}
    assert baseline.get("upload_id", "").startswith("md-seed-")
    assert baseline.get("baseline")
    assert baseline.get("source") == "factory_seed"


def test_canonical_workbook_has_all_entities():
    from app.livewell.seed_service import load_canonical_payload

    payload = load_canonical_payload()
    assert payload.get("rubric", {}).get("categories")
    assert payload.get("solutions", {}).get("solutions")
    assert payload.get("catalog", {}).get("products")


def test_seed_missing_defaults_skips_existing():
    cfg, seeded = seed_missing_defaults(
        {
            "home_safety_rubric": {
                "categories": [
                    {
                        "id": "x",
                        "title": "X",
                        "maxPoints": 1,
                        "items": [{"id": "i", "label": "I", "maxPoints": 1}],
                    }
                ]
            }
        },
        only=("rubric",),
    )
    assert seeded == []
