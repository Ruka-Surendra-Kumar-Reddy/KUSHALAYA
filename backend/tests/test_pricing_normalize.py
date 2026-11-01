from app.livewell.pricing_service import normalize_pricing


def test_normalize_pricing_defaults_and_clamps():
    out = normalize_pricing({})
    assert out["default_margin_percent"] == 25
    assert out["gst_percent"] == 18
    assert out["margin_type"] == "percent"
    assert out["round_off_rule"] == "nearest_100"
    assert out["default_labor_hours_per_solution"] == 2


def test_normalize_pricing_invalid_enums_and_negatives():
    out = normalize_pricing(
        {
            "margin_type": "bonus",
            "round_off_rule": "nearest_1",
            "default_margin_percent": 250,
            "min_margin_percent": -5,
            "fixed_margin_inr": -10,
            "gst_percent": 18,
            "use_vendor_cost_for_margin": 1,
        }
    )
    assert out["margin_type"] == "percent"
    assert out["round_off_rule"] == "nearest_100"
    assert out["default_margin_percent"] == 100
    assert out["min_margin_percent"] == 0
    assert out["fixed_margin_inr"] == 0
    assert out["use_vendor_cost_for_margin"] is True


def test_normalize_pricing_fixed_margin():
    out = normalize_pricing({"margin_type": "fixed", "round_off_rule": "none", "fixed_margin_inr": 500})
    assert out["margin_type"] == "fixed"
    assert out["round_off_rule"] == "none"
    assert out["fixed_margin_inr"] == 500
