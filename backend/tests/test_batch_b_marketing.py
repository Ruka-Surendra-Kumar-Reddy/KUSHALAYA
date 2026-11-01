"""Batch B — marketing-site form validation, custom plan, public stats scope, settings checks."""

import pytest

from app.api.v1 import public_enquiries as mod
from app.models.elder import Elder
from app.models.elder_prospect import ElderProspect
from app.models.tenant import Tenant

URL = "/api/v1/home-safety/enquiries"


def _login(client, email):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _enquire(client, **over):
    body = {"name": "Anita Rao", "phone": "+91 90000 00000", "kind": "care-check"}
    body.update(over)
    return client.post(URL, json=body)


@pytest.mark.parametrize("phone", ["12345", "5876543210", "+91 12345 67890", "phone me", "+1 23"])
def test_bad_phone_rejected(client, seed_tenant, phone):
    res = _enquire(client, phone=phone)
    assert res.status_code == 422
    assert "mobile number" in res.text


@pytest.mark.parametrize(
    "phone,stored",
    [
        ("98765-43210", "+91 98765 43210"),
        ("09876543210", "+91 98765 43210"),
        ("+91 98765 43210", "+91 98765 43210"),
        ("+44 7911 123456", "+447911123456"),
    ],
)
def test_good_phone_normalised(client, db, seed_tenant, phone, stored):
    assert _enquire(client, phone=phone).status_code == 200
    assert db.query(ElderProspect).order_by(ElderProspect.id.desc()).first().phone == stored


@pytest.mark.parametrize("email", ["x@y", "not-an-email", "a@@b.com"])
def test_bad_email_rejected(client, seed_tenant, email):
    assert _enquire(client, phone=None, email=email).status_code == 422


@pytest.mark.parametrize("pin", ["12345", "900001", "000123", "50008a"])
def test_bad_pincode_rejected(client, seed_tenant, pin):
    res = _enquire(client, pincode=pin)
    assert res.status_code == 422
    assert "PIN" in res.text


def test_blank_custom_plan_rejected(client, seed_tenant):
    res = _enquire(client, kind="custom-plan", services=[], products=[], visit_frequency="")
    assert res.status_code == 422
    assert "at least one" in res.text
    ok = _enquire(client, kind="custom-plan", services=["Nursing visits"], phone="+91 90000 00001")
    assert ok.status_code == 200, ok.text


def test_public_stats_only_count_site_tenant(client, db, seed_tenant):
    tid = seed_tenant["tenant"].id
    other = Tenant(name="Other agency", email="ob@test.example", phone="1", address="a", city="c", state="s")
    db.add(other)
    db.flush()
    for i in range(5):
        db.add(Elder(tenant_id=tid, first_name="Mine", last_name=str(i), status="ACTIVE"))
    for i in range(10):
        db.add(Elder(tenant_id=other.id, first_name="Theirs", last_name=str(i), status="ACTIVE"))
    db.commit()
    mod._stats_cache["value"] = None
    try:
        mine = db.query(Elder).filter(Elder.tenant_id == tid, Elder.status == "ACTIVE").count()
        body = client.get(f"{URL}/stats").json()
        assert body["families"] == (mine // 5) * 5
        assert body["families"] < mine + 10
    finally:
        mod._stats_cache["value"] = None


def test_settings_grievance_email_and_phone(client, seed_tenant):
    headers = _login(client, "admin@test.example")
    bad = client.put(
        "/api/v1/site-settings",
        json={"company": {"grievance_email": "not an email"}},
        headers=headers,
    )
    assert bad.status_code == 400
    bad_phone = client.put(
        "/api/v1/site-settings",
        json={"company": {"grievance_phone": "123"}},
        headers=headers,
    )
    assert bad_phone.status_code == 400
    ok = client.put(
        "/api/v1/site-settings",
        json={"company": {"grievance_email": "grievance@kushalaya.com", "grievance_phone": "98765-43210"}},
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["company"]["grievance_phone"] == "+91 98765 43210"
