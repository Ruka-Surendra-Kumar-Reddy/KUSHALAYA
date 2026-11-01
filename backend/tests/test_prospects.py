from app.core.security import hash_password
from app.models.user import User


def test_elder_prospect_pipeline(db, client, seed_tenant):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "manager@test.example", "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    create = client.post(
        "/api/v1/prospects/elders",
        headers=headers,
        json={
            "first_name": "Prospect",
            "last_name": "Client",
            "phone": "+1-555-9999",
            "source": "referral",
            "notes": "Inbound call",
        },
    )
    assert create.status_code == 200
    pid = create.json()["id"]
    assert create.json()["stage"] == "NEW"
    assert create.json()["status"] == "OPEN"

    stage = client.patch(
        f"/api/v1/prospects/elders/{pid}/stage",
        headers=headers,
        json={"stage": "CONTACTED"},
    )
    assert stage.status_code == 200
    assert stage.json()["stage"] == "CONTACTED"

    activity = client.post(
        f"/api/v1/prospects/elders/{pid}/activities",
        headers=headers,
        json={"activity_type": "CALL", "body": "Left voicemail"},
    )
    assert activity.status_code == 200

    activities = client.get(
        f"/api/v1/prospects/elders/{pid}/activities",
        headers=headers,
    )
    assert activities.status_code == 200
    assert len(activities.json()) >= 2

    follow = client.patch(
        f"/api/v1/prospects/elders/{pid}",
        headers=headers,
        json={"next_follow_up_at": "2026-01-15T10:00:00"},
    )
    assert follow.status_code == 200

    convert = client.post(
        f"/api/v1/prospects/elders/{pid}/convert",
        headers=headers,
    )
    assert convert.status_code == 200
    elder_id = convert.json()["elder_id"]
    assert convert.json().get("prospect_absorbed") is True
    assert convert.json()["prospect"]["status"] == "WON"

    # Prospect row is absorbed — no longer in the pipeline.
    gone = client.get(f"/api/v1/prospects/elders/{pid}", headers=headers)
    assert gone.status_code == 404

    elder = client.get(f"/api/v1/elders/{elder_id}", headers=headers)
    assert elder.status_code == 200
    assert elder.json()["first_name"] == "Prospect"


def test_caregiver_prospect_lost(db, client, seed_tenant):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "manager@test.example", "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    create = client.post(
        "/api/v1/prospects/caregivers",
        headers=headers,
        json={
            "first_name": "Recruit",
            "last_name": "Candidate",
            "stage": "APPLIED",
        },
    )
    assert create.status_code == 200
    pid = create.json()["id"]

    lost = client.patch(
        f"/api/v1/prospects/caregivers/{pid}/stage",
        headers=headers,
        json={"stage": "REJECTED", "lost_reason": "Failed background check"},
    )
    assert lost.status_code == 200
    assert lost.json()["status"] == "LOST"
    assert lost.json()["lost_reason"] == "Failed background check"

    convert = client.post(
        f"/api/v1/prospects/caregivers/{pid}/convert",
        headers=headers,
    )
    assert convert.status_code == 400


def test_prospect_stages_and_owners(db, client, seed_tenant):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "manager@test.example", "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    stages = client.get("/api/v1/prospects/stages", headers=headers)
    assert stages.status_code == 200
    assert "NEW" in stages.json()["elder_stages"]
    assert "APPLIED" in stages.json()["caregiver_stages"]

    owners = client.get("/api/v1/prospects/owners", headers=headers)
    assert owners.status_code == 200
    assert any(o["email"] == "manager@test.example" for o in owners.json())
