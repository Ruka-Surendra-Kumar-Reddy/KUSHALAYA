"""Caregiver portal API: staff create the login, the caregiver sees only their own day."""

from app.models.assignment import Assignment
from app.models.elder_location import ElderLocation


def _login(client, email, password="carepass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _setup(client, db, seed_tenant, auth_headers):
    cg = seed_tenant["caregiver"]
    elder = seed_tenant["elder"]
    db.add(
        Assignment(
            tenant_id=cg.tenant_id,
            elder_id=elder.id,
            caregiver_id=cg.id,
            status="ACTIVE",
            match_score=90.0,
        )
    )
    db.add(
        ElderLocation(
            tenant_id=cg.tenant_id,
            elder_id=elder.id,
            latitude=17.4,
            longitude=78.4,
            radius_meters=100.0,
        )
    )
    db.commit()
    res = client.post(
        f"/api/v1/caregivers/{cg.id}/portal-account",
        json={"email": "cg.portal@test.example", "password": "carepass123"},
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    return _login(client, "cg.portal@test.example")


def test_caregiver_sees_own_day_and_pay(client, db, seed_tenant, auth_headers):
    headers = _setup(client, db, seed_tenant, auth_headers)

    me = client.get("/api/v1/caregiver-portal/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["caregiver_id"] == seed_tenant["caregiver"].id

    shifts = client.get("/api/v1/caregiver-portal/shifts/today", headers=headers).json()
    assert len(shifts) == 1
    assert shifts[0]["elder_id"] == seed_tenant["elder"].id
    assert shifts[0]["geofence"]["configured"] is True

    earnings = client.get("/api/v1/caregiver-portal/earnings", headers=headers)
    assert earnings.status_code == 200
    assert earnings.json()["finalized_runs_count"] == 0
    assert client.get("/api/v1/caregiver-portal/payslips", headers=headers).json() == []


def test_caregiver_check_in_at_the_home(client, db, seed_tenant, auth_headers):
    headers = _setup(client, db, seed_tenant, auth_headers)
    device = "web-test-device-0001"
    assert (
        client.post(
            "/api/v1/caregiver-portal/device",
            json={"device_id": device, "device_label": "Test phone"},
            headers=headers,
        ).status_code
        == 200
    )
    res = client.post(
        "/api/v1/caregiver-portal/location-events",
        json={
            "elder_id": seed_tenant["elder"].id,
            "event_type": "CHECKIN",
            "latitude": 17.4,
            "longitude": 78.4,
            "accuracy": 10,
            "device_id": device,
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["within_geofence"] is True


def test_staff_cannot_use_caregiver_portal(client, auth_headers):
    assert client.get("/api/v1/caregiver-portal/me", headers=auth_headers).status_code == 403


def test_viewer_cannot_create_caregiver_login(client, seed_tenant):
    headers = _login(client, "viewer@test.example", "testpass123")
    res = client.post(
        f"/api/v1/caregivers/{seed_tenant['caregiver'].id}/portal-account",
        json={"email": "x@test.example", "password": "carepass123"},
        headers=headers,
    )
    assert res.status_code == 403
