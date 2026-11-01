"""Products, coupons and orders: cost + margin, GST on top, discount rules, never below cost."""

from app.livewell.commerce import price_paise


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _priced_product(client, admin, name="Fixed grab bar", cost=100000, margin_bp=3000):
    products = client.get("/api/v1/products", headers=admin).json()
    p = next(x for x in products if x["name"] == name)
    res = client.put(f"/api/v1/products/{p['id']}", json={"cost_paise": cost, "margin_bp": margin_bp}, headers=admin)
    assert res.status_code == 200, res.text
    return res.json()


def test_nine_default_products_and_price():
    assert price_paise(100000, 3000) == 130000  # ₹1,000 + 30% = ₹1,300


def test_admin_sets_cost_and_margin(client, seed_tenant):
    admin = _login(client, "admin@test.example")
    products = client.get("/api/v1/products", headers=admin).json()
    assert len(products) == 117  # 9 originals + catalog (PM-004 is listed but off)
    p = _priced_product(client, admin)
    assert p["price_paise"] == 130000


def test_manager_cannot_change_prices(client, seed_tenant, auth_headers):
    products = client.get("/api/v1/products", headers=auth_headers).json()
    res = client.put(f"/api/v1/products/{products[0]['id']}", json={"cost_paise": 1}, headers=auth_headers)
    assert res.status_code == 403


def test_order_gst_on_top_and_manager_discount_limit(client, seed_tenant, auth_headers):
    admin = _login(client, "admin@test.example")
    p = _priced_product(client, admin)
    elder_id = seed_tenant["elder"].id

    ok = client.post(
        "/api/v1/orders",
        json={"elder_id": elder_id, "lines": [{"product_id": p["id"], "qty": 1}], "discount_bp": 1000},
        headers=auth_headers,
    ).json()
    assert ok["status"] == "approved"
    assert ok["discount_paise"] == 13000
    assert ok["gst_paise"] == (130000 - 13000) * 18 // 100
    assert ok["total_paise"] == 117000 + ok["gst_paise"]

    big = client.post(
        "/api/v1/orders",
        json={"elder_id": elder_id, "lines": [{"product_id": p["id"], "qty": 1}], "discount_bp": 2000},
        headers=auth_headers,
    ).json()
    assert big["status"] == "pending_approval"
    assert client.post(f"/api/v1/orders/{big['id']}/status", json={"status": "approved"}, headers=auth_headers).status_code == 403
    approved = client.post(f"/api/v1/orders/{big['id']}/status", json={"status": "approved"}, headers=admin)
    assert approved.json()["status"] == "approved"


def test_never_below_cost(client, seed_tenant):
    admin = _login(client, "admin@test.example")
    p = _priced_product(client, admin)
    res = client.post(
        "/api/v1/orders",
        json={"elder_id": seed_tenant["elder"].id, "lines": [{"product_id": p["id"]}], "discount_bp": 4000},
        headers=admin,
    )
    assert res.status_code == 400
    assert "below cost" in res.text


def test_coupon_applies_and_counts(client, seed_tenant, auth_headers):
    admin = _login(client, "admin@test.example")
    p = _priced_product(client, admin)
    c = client.post("/api/v1/coupons", json={"code": "diwali10", "kind": "percent", "value": 1000, "max_uses": 1}, headers=admin)
    assert c.status_code == 201, c.text
    assert c.json()["code"] == "DIWALI10"
    order = client.post(
        "/api/v1/orders",
        json={"elder_id": seed_tenant["elder"].id, "lines": [{"product_id": p["id"]}], "coupon_code": "DIWALI10"},
        headers=auth_headers,
    ).json()
    assert order["status"] == "approved" and order["discount_paise"] == 13000
    again = client.post(
        "/api/v1/orders/quote",
        json={"lines": [{"product_id": p["id"]}], "coupon_code": "DIWALI10"},
        headers=auth_headers,
    )
    assert again.status_code == 400 and "used up" in again.text


def test_catalog_backfill_keeps_existing_rows(db, seed_tenant):
    """Old tenants (9 rows, no codes) get the rest of the catalog; their rows and prices stay."""
    from app.livewell.commerce import catalog_products, ensure_default_products, product_image_url
    from app.models.commerce import Product

    tid = seed_tenant["tenant"].id
    db.add(Product(tenant_id=tid, name="Fixed grab bar", category="Bathroom", cost_paise=111100))
    db.add(Product(tenant_id=tid, name="Anti-slip bath mat", category="Bathroom"))
    db.commit()

    ensure_default_products(db, tid)
    ensure_default_products(db, tid)  # idempotent

    rows = db.query(Product).filter(Product.tenant_id == tid).all()
    by_name = {p.name: p for p in rows}
    assert len(rows) == len(by_name)
    assert by_name["Fixed grab bar"].cost_paise == 111100
    assert by_name["Fixed grab bar"].product_code == "BTH-001"
    assert "Straight Grab Bar" not in by_name  # same product as "Fixed grab bar"
    assert len(rows) == 2 + len(catalog_products()) - 1
    oxi = by_name["Pulse oximeter"]
    assert price_paise(oxi.cost_paise, oxi.margin_bp) == 150000
    assert product_image_url(oxi) == "/marketing/products/catalog/hlt-002.webp"
    assert product_image_url(by_name["Home Nursing (24 hr)"]) == "/marketing/products/catalog/nur-003.webp"  # each service has its own image


def test_catalog_prices_match_workbook():
    import json
    from pathlib import Path

    from app.livewell.commerce import catalog_products

    listed = {p["product_code"]: p["price_inr"] for p in json.loads(
        (Path(__file__).parents[1] / "app/livewell/default_catalog.json").read_text(encoding="utf-8"))["products"]}
    for p in catalog_products():
        if p["product_code"] in listed and p["active"]:
            assert price_paise(p["cost_paise"], p["margin_bp"]) == listed[p["product_code"]] * 100, p["name"]


def test_every_catalog_image_exists():
    from pathlib import Path

    from app.livewell.commerce import catalog_image_url, catalog_products

    public = Path(__file__).parents[2] / "frontend" / "public"
    for p in catalog_products():
        url = catalog_image_url(p["product_code"])
        assert (public / url.lstrip("/")).is_file(), url


def test_unpriced_product_cannot_be_ordered(client, seed_tenant, auth_headers):
    """'Price on request' items are never sold at ₹0."""
    admin = _login(client, "admin@test.example")
    p = _priced_product(client, admin, cost=0, margin_bp=3000)
    assert p["price_paise"] == 0
    res = client.post(
        "/api/v1/orders",
        json={"elder_id": seed_tenant["elder"].id, "lines": [{"product_id": p["id"], "qty": 1}]},
        headers=auth_headers,
    )
    assert res.status_code == 400
    assert "no price yet" in res.json()["detail"]
