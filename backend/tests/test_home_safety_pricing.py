from app.livewell.pricing_defaults import DEFAULT_PRICING
from app.livewell.pricing_service import normalize_pricing


def test_normalize_pricing_defaults():
    out = normalize_pricing({})
    assert out["default_margin_percent"] == DEFAULT_PRICING["default_margin_percent"]
    assert out["gst_percent"] == 18
    assert out["round_off_rule"] == "nearest_100"


def test_pricing_api_get_and_save(client, admin_headers, seed_tenant):
    res = client.get("/api/v1/home-safety/pricing", headers=admin_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["labor_rate_per_hour_inr"] == 700

    updated = {**body, "labor_rate_per_hour_inr": 900, "default_margin_percent": 30}
    save = client.put("/api/v1/home-safety/pricing", headers=admin_headers, json=updated)
    assert save.status_code == 200
    assert save.json()["labor_rate_per_hour_inr"] == 900
    assert save.json()["default_margin_percent"] == 30

    again = client.get("/api/v1/home-safety/pricing", headers=admin_headers)
    assert again.json()["labor_rate_per_hour_inr"] == 900
