from app.livewell.ai_config_service import (
    filter_solutions_by_tier,
    normalize_ai_config,
    solutions_for_tier,
)


def test_normalize_ai_config_filters_invalid_tiers():
    out = normalize_ai_config(
        {
            "tiers": [
                {"id": "essential", "name": "Essential", "sort_order": 1},
                {"id": "nope", "name": "Bad"},
                {"id": "premium", "active": False},
            ]
        }
    )
    ids = [t["id"] for t in out["tiers"]]
    assert "essential" in ids
    assert "nope" not in ids
    assert "premium" not in ids


def test_solutions_for_tier_from_spreadsheet_rows():
    cfg = {
        "package_solutions": [
            {"tier_id": "comfort", "room_type": "bathroom", "solution_id": "S1", "active": True},
            {"tier_id": "comfort", "room_type": "kitchen", "solution_id": "S2"},
            {"tier_id": "essential", "room_type": "bathroom", "solution_id": "S0"},
        ]
    }
    assert solutions_for_tier(cfg, room_type="Bathroom", tier_id="Comfort") == ["S1"]
    assert solutions_for_tier(cfg, room_type="bedroom", tier_id="comfort") == []


def test_filter_solutions_by_tier_fallback_thirds():
    ids = ["a", "b", "c", "d", "e", "f"]
    assert filter_solutions_by_tier({}, room_type="bath", tier_id="essential", assessment_solution_ids=ids) == [
        "a",
        "b",
    ]
    assert filter_solutions_by_tier({}, room_type="bath", tier_id="comfort", assessment_solution_ids=ids) == [
        "a",
        "b",
        "c",
        "d",
    ]
    assert (
        filter_solutions_by_tier({}, room_type="bath", tier_id="premium", assessment_solution_ids=ids)
        == ids
    )
    assert filter_solutions_by_tier({}, room_type="bath", tier_id="essential", assessment_solution_ids=[]) == []
