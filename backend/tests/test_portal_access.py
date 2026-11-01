"""Portal accounts must not access staff admin APIs."""

from app.core.security import hash_password
from app.models.user import User


def _login(client, email, password="testpass123"):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_elder_portal_blocked_from_staff_apis(db, client, seed_tenant):
    elder = seed_tenant["elder"]
    user = User(
        email="family.blocked@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Family",
        last_name="User",
        role="ELDER_PORTAL",
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
    )
    db.add(user)
    db.commit()

    headers = _login(client, user.email)

    assert client.get("/api/v1/elders", headers=headers).status_code == 403
    assert (
        client.get("/api/v1/prospects/elders", headers=headers).status_code == 403
    )
    assert client.get("/api/v1/geocode?address=test", headers=headers).status_code == 403
    me = client.get("/api/v1/elder-portal/me", headers=headers)
    if me.status_code == 404:
        import pytest
        pytest.skip("Elder portal API is not mounted in this LiveWell deploy")
    assert me.status_code == 200


def test_caregiver_portal_blocked_from_staff_apis(db, client, seed_tenant):
    caregiver = seed_tenant["caregiver"]
    user = User(
        email="cg.blocked@test.example",
        password_hash=hash_password("testpass123"),
        first_name="CG",
        last_name="Portal",
        role="CAREGIVER",
        tenant_id=caregiver.tenant_id,
        caregiver_id=caregiver.id,
    )
    db.add(user)
    db.commit()

    headers = _login(client, user.email)

    assert client.get("/api/v1/caregivers", headers=headers).status_code == 403
    assert (
        client.get("/api/v1/prospects/caregivers", headers=headers).status_code == 403
    )
    me = client.get("/api/v1/caregiver-portal/me", headers=headers)
    if me.status_code == 404:
        import pytest
        pytest.skip("Caregiver portal API is not mounted in this LiveWell deploy")
    assert me.status_code == 200


def test_register_open_blocked_in_production(client, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")
    res = client.post(
        "/api/v1/auth/register-open",
        json={
            "email": "open@test.example",
            "password": "testpass123",
            "first_name": "Open",
            "last_name": "User",
            "tenant_id": 1,
            "role": "CARE_MANAGER",
        },
    )
    assert res.status_code == 400
