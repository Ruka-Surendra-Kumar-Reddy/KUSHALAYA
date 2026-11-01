"""Family Requests page: the whole on-sale catalog (same as ops Products), no cost/margin,
and a request for a catalog item carries its id and code through to staff."""

from tests.test_phase2f_money_profile import F, _family_user, _login

CARE = "/api/v1/home-safety/care"


def _ops_on_sale(client):
    admin = _login(client, "admin@test.example")
    return admin, [p for p in client.get("/api/v1/products", headers=admin).json() if p["active"]]


def test_family_catalog_is_every_on_sale_item_without_cost(client, db, seed_tenant):
    fam = _login(client, _family_user(db, seed_tenant["elder"], tag="cat1").email)
    rows = client.get(f"{F}/products", headers=fam).json()
    _admin, ops = _ops_on_sale(client)
    assert len(rows) == len(ops) > 100
    assert {r["id"] for r in rows} == {p["id"] for p in ops}
    assert {r["kind"] for r in rows} == {"product", "service"}
    for r in rows:
        assert not any("cost" in k or "margin" in k for k in r), r
        assert r["price_paise"] >= 0
        assert r["price_with_gst_paise"] == r["price_paise"] + r["price_paise"] * 1800 // 10000
        assert r["description"], f"no plain-language line for {r['name']}"
        assert r["included"]
    # Services from the catalog (nursing, transport...) are there, not just safety products.
    assert any(r["category"] == "Nursing" and r["kind"] == "service" for r in rows)
    assert all(r["image_url"] for r in rows if r["product_code"])


def test_request_for_catalog_item_reaches_staff_with_code(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _login(client, _family_user(db, elder, tag="cat2").email)
    rows = client.get(f"{F}/products", headers=fam).json()
    nurse = next(r for r in rows if r["kind"] == "service" and r["category"] == "Nursing")
    bar = next(r for r in rows if r["kind"] == "product" and r["product_code"])

    # service_type from the page is a hint; the catalog row decides product vs service.
    res = client.post(f"{F}/service-requests", headers=fam, json={"service_type": "product", "product_id": nurse["id"]})
    assert res.status_code == 200, res.text
    made = res.json()
    assert made["service_type"] == "catalog_service"
    assert made["product_id"] == nurse["id"] and made["product_code"] == nurse["product_code"]
    assert made["service_label"] == f"Service: {nurse['name']}"

    res = client.post(f"{F}/service-requests", headers=fam, json={"service_type": "product", "product_id": bar["id"]})
    assert res.status_code == 200, res.text
    assert res.json()["service_label"] == f"Product: {bar['name']}"

    admin, _ = _ops_on_sale(client)
    staff = client.get(f"{CARE}/elders/{elder.id}/service-requests", headers=admin).json()
    codes = {r["product_code"] for r in staff}
    assert {nurse["product_code"], bar["product_code"]} <= codes
    # A made-up id is refused rather than sent as a blank request.
    bad = client.post(f"{F}/service-requests", headers=fam, json={"service_type": "product", "product_id": 999999})
    assert bad.status_code == 400
