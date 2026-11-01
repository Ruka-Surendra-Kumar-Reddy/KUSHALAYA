"""Partner / supplier ratings are stored to one decimal — what the UI shows."""

from app.livewell.supplier_service import normalize_supplier_directory


def test_supplier_ratings_rounded_to_one_decimal():
    out = normalize_supplier_directory(
        {
            "suppliers": [
                {"id": "s1", "name": "A", "rating": 4.333333, "rolling_rating": 3.75, "rolling_rating_count": 3},
                {"id": "s2", "name": "B", "rating": "4.26", "rolling_rating": None},
                {"id": "s3", "name": "C", "rating": 7, "rolling_rating": -1},
            ]
        }
    )
    by_id = {s["id"]: s for s in out["suppliers"]}
    assert by_id["s1"]["rating"] == 4.3
    assert by_id["s1"]["rolling_rating"] == 3.8
    assert by_id["s2"]["rating"] == 4.3
    assert by_id["s2"]["rolling_rating"] is None
    assert by_id["s3"]["rating"] == 5.0
    assert by_id["s3"]["rolling_rating"] == 0.0


def test_rolling_rating_recompute_rounds_to_one_decimal(db, seed_tenant, monkeypatch):
    from app.livewell import partner_rating_service as prs
    from app.livewell.config_keys import SUPPLIERS_KEY

    tenant = seed_tenant["tenant"]
    tenant.workflow_config = {
        **(tenant.workflow_config or {}),
        SUPPLIERS_KEY: {"suppliers": [{"id": "p1", "name": "Partner", "rolling_window": 5}], "offers": []},
    }
    db.commit()

    monkeypatch.setattr(
        prs,
        "collect_partner_experience_ratings",
        lambda db_, tid, pid: [
            {"visit_id": "a", "visited_at": "2026-09-01", "rating": 5, "comment": "", "visit_type": ""},
            {"visit_id": "b", "visited_at": "2026-09-02", "rating": 4, "comment": "", "visit_type": ""},
            {"visit_id": "c", "visited_at": "2026-09-03", "rating": 4, "comment": "", "visit_type": ""},
        ],
    )
    target = prs.recompute_partner_rolling_rating(db, tenant.id, "p1")
    assert target["rolling_rating"] == 4.3  # 13/3 = 4.333…
    assert target["rolling_rating_count"] == 3
