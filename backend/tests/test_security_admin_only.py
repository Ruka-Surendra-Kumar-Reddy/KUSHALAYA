"""Security fix 2026-10-07: global settings + business data are admin-only; no plain passwords."""

import pytest

from app.livewell.iot_broker_settings import get_broker_settings
from app.main import api_docs_urls
from app.models.iot_device import IotHub

ADMIN_ONLY = [
    ("get", "/api/v1/iot/broker-settings"),
    ("put", "/api/v1/iot/broker-settings"),
    ("post", "/api/v1/iot/broker-settings/load-credentials-file"),
    ("post", "/api/v1/iot/broker-settings/apply-mosquitto"),
    ("get", "/api/v1/iot/minewlink-preview?mac_address=AA:BB:CC:DD:EE:FF"),
    ("put", "/api/v1/home-safety/catalog"),
    ("post", "/api/v1/home-safety/catalog/products/p1/image"),
    ("delete", "/api/v1/home-safety/catalog/products/p1/images/1"),
    ("delete", "/api/v1/home-safety/catalog/products/p1/image"),
    ("put", "/api/v1/home-safety/rubric"),
    ("put", "/api/v1/home-safety/pricing"),
    ("put", "/api/v1/home-safety/suppliers"),
    ("put", "/api/v1/home-safety/solutions"),
    ("post", "/api/v1/home-safety/master-data/import"),
    ("put", "/api/v1/home-safety/master-data/import/1/pricing"),
    ("post", "/api/v1/home-safety/master-data/import/approve"),
    ("post", "/api/v1/home-safety/master-data/rollback/1"),
    ("post", "/api/v1/home-safety/master-data/seed-defaults"),
    ("get", "/api/v1/coupons"),
]

HUB_SECRET = "hub-s3cret-pw"
INGESTOR_SECRET = "ingest-s3cret-pw"


def _broker_body(**over):
    body = {
        "broker_host": "mqtt.example.test",
        "broker_port": 8883,
        "tls": True,
        "hub_username": "mg7_home1",
        "hub_password": HUB_SECRET,
        "ingestor_username": "livewell_ingestor",
        "ingestor_password": INGESTOR_SECRET,
    }
    body.update(over)
    return body


@pytest.mark.parametrize("method,path", ADMIN_ONLY)
def test_manager_gets_403(client, auth_headers, method, path):
    kwargs = {"headers": auth_headers}
    if method in ("put", "post") and "/image" not in path and "/import" not in path:
        kwargs["json"] = {}
    res = getattr(client, method)(path, **kwargs)
    assert res.status_code == 403, (method, path, res.status_code, res.text)


def test_manager_products_have_no_cost_or_margin(client, auth_headers, admin_headers):
    mine = client.get("/api/v1/products", headers=auth_headers)
    assert mine.status_code == 200
    rows = mine.json()
    assert rows and all("price_paise" in p for p in rows)
    assert not any(k in p for p in rows for k in ("cost_paise", "margin_bp", "margin_paise"))
    admin_rows = client.get("/api/v1/products", headers=admin_headers).json()
    assert all("cost_paise" in p and "margin_bp" in p for p in admin_rows)


def test_manager_quote_and_orders_hide_cost(client, seed_tenant, auth_headers, admin_headers):
    p = client.get("/api/v1/products", headers=admin_headers).json()[0]
    client.put(f"/api/v1/products/{p['id']}", json={"cost_paise": 100000, "margin_bp": 3000}, headers=admin_headers)
    elder_id = seed_tenant["elder"].id
    quote = client.post("/api/v1/orders/quote", json={"lines": [{"product_id": p["id"], "qty": 1}]}, headers=auth_headers)
    assert quote.status_code == 200, quote.text
    assert "cost_paise" not in quote.text and "margin_paise" not in quote.text
    assert quote.json()["total_paise"] > 0
    made = client.post(
        "/api/v1/orders", json={"elder_id": elder_id, "lines": [{"product_id": p["id"], "qty": 1}]}, headers=auth_headers
    )
    assert made.status_code == 201, made.text
    assert "cost_paise" not in made.text and "margin_paise" not in made.text
    listed = client.get(f"/api/v1/orders?elder_id={elder_id}", headers=auth_headers)
    assert listed.status_code == 200 and "cost_paise" not in listed.text
    admin_view = client.get(f"/api/v1/orders?elder_id={elder_id}", headers=admin_headers).json()
    assert admin_view and "margin_paise" in admin_view[0]


def test_broker_settings_never_return_plain_passwords(client, db, admin_headers):
    saved = client.put("/api/v1/iot/broker-settings", json=_broker_body(), headers=admin_headers)
    assert saved.status_code == 200, saved.text
    assert HUB_SECRET not in saved.text and INGESTOR_SECRET not in saved.text

    got = client.get("/api/v1/iot/broker-settings", headers=admin_headers)
    assert got.status_code == 200
    body = got.json()
    assert HUB_SECRET not in got.text and INGESTOR_SECRET not in got.text
    assert body["hub_password"] == "" and body["hub_password_set"] is True
    assert body["ingestor_password_set"] is True and body["hub_password_masked"]

    # Blank password on save keeps the stored one.
    again = client.put(
        "/api/v1/iot/broker-settings",
        json=_broker_body(hub_password="", ingestor_password="", broker_host="mqtt2.example.test"),
        headers=admin_headers,
    )
    assert again.status_code == 200, again.text
    stored = get_broker_settings(db)
    assert stored["broker_host"] == "mqtt2.example.test"
    assert stored["hub_password"] == HUB_SECRET and stored["ingestor_password"] == INGESTOR_SECRET

    fromfile = client.post("/api/v1/iot/broker-settings/load-credentials-file", headers=admin_headers)
    assert fromfile.status_code == 200 and fromfile.json()["hub_password"] == ""


def test_hub_secret_only_for_admins(client, db, seed_tenant, auth_headers, admin_headers):
    db.add(
        IotHub(
            tenant_id=seed_tenant["tenant"].id,
            home_key="home1",
            hub_key="mg7-sec",
            label="Hub",
            mqtt_username="mg7_sec",
            mqtt_password="hub-row-secret",
            mqtt_topic="t",
        )
    )
    db.commit()
    mine = client.get("/api/v1/iot/hubs", headers=auth_headers)
    assert mine.status_code == 200 and mine.json()
    assert "hub-row-secret" not in mine.text and "mqtt_password" not in mine.text
    admin = client.get("/api/v1/iot/hubs", headers=admin_headers).json()
    assert admin[0]["mqtt_password"] == "hub-row-secret"


def test_admin_can_still_write_rubric_and_pricing(client, admin_headers):
    rubric = client.get("/api/v1/home-safety/rubric", headers=admin_headers).json()
    # The role gate passes (the default rubric may fail content validation, which is fine here).
    assert client.put("/api/v1/home-safety/rubric", json=rubric, headers=admin_headers).status_code != 403
    pricing = client.get("/api/v1/home-safety/pricing", headers=admin_headers).json()
    assert client.put("/api/v1/home-safety/pricing", json=pricing, headers=admin_headers).status_code == 200
    assert client.get("/api/v1/coupons", headers=admin_headers).status_code == 200


def test_docs_disabled_in_production():
    off = api_docs_urls("production")
    assert off == {"docs_url": None, "redoc_url": None, "openapi_url": None}
    on = api_docs_urls("development")
    assert on["docs_url"] == "/docs" and on["openapi_url"] == "/openapi.json"


def test_docs_disabled_on_a_production_app():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    prod = FastAPI(**api_docs_urls("production"))
    with TestClient(prod) as c:
        assert c.get("/docs").status_code == 404
        assert c.get("/redoc").status_code == 404
        assert c.get("/openapi.json").status_code == 404
