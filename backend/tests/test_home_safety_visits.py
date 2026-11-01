"""Safe Home visit logging — separate from caregiver attendance."""

from app.core.security import hash_password
from app.models.elder import Elder
from app.models.user import User


def test_family_visits_safe_home_only(db, client, seed_tenant, auth_headers):
    elder = db.query(Elder).first()

    create = client.post(
        "/api/v1/home-safety/visits",
        headers=auth_headers,
        json={
            "elder_id": elder.id,
            "visit_type": "Wellness visit",
            "staff_name": "Nurse Test",
            "summary": "All good today.",
            "wellness_notes": "BP normal.",
            "concerns": ["None"],
            "recommendations": "Keep routine.",
            "duration_minutes": 30,
            "baseline": {
                "typical_mobility": "Independent with cane outdoors",
                "usual_wake_time": "6:30 AM",
                "notes": "Baseline from first visit",
            },
            "checkin": {
                "overall": "normal",
                "mood": "normal",
                "mobility": "normal_for_them",
                "eating": "normal",
                "medication": "none",
                "contact_outcome": "answered_normal",
                "care_manager_note": "Seemed fine.",
                "family_message": "Mom is doing well today — walking with her cane as usual.",
            },
        },
    )
    assert create.status_code == 200
    body = create.json()
    visit_id = body["id"]
    assert body["visit_type"] == "Baseline profile"
    assert body.get("checkin", {}).get("overall") == "normal"
    assert body.get("stability_score") == 50
    assert body.get("stability", {}).get("band") == "baseline"
    assert "Mom is doing well" in (body.get("family_message") or "")

    family = User(
        email="family.visits@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Family",
        last_name="Visits",
        role="ELDER_PORTAL",
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
    )
    db.add(family)
    db.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": family.email, "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    listed = client.get("/api/v1/home-safety/family/visits", headers=headers)
    assert listed.status_code == 200
    ids = [v["id"] for v in listed.json()]
    assert visit_id in ids

    detail = client.get(f"/api/v1/home-safety/family/visits/{visit_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["summary"] == "All good today."
    assert detail.json()["concerns"] == ["None"]
    assert "Mom is doing well" in (detail.json().get("family_message") or "")

    dash = client.get("/api/v1/home-safety/family/dashboard", headers=headers)
    assert dash.status_code == 200
    care = dash.json().get("care_status")
    assert care is not None
    assert care["level"] == "ok"
    assert "OK" in care["headline"] or "is OK" in care["headline"]
    snap = care.get("snapshot") or {}
    assert "Mom is doing well" in (snap.get("family_message") or snap.get("care_manager_note") or "")

    # Stability history is on the family dashboard for trend graphing
    assert care.get("stability_score") == 50 or dash.json().get("latest_stability_score") == 50
    hist = dash.json().get("stability_score_history") or []
    assert any(int(p.get("score") or 0) == 50 for p in hist)

    baseline = client.get(
        f"/api/v1/home-safety/visits/baseline/{elder.id}",
        headers=auth_headers,
    )
    assert baseline.status_code == 200
    assert baseline.json()["typical_mobility"]
    assert baseline.json()["updated_at"]


def test_first_visit_requires_baseline(db, client, seed_tenant, auth_headers):
    elder = db.query(Elder).first()
    missing = client.post(
        "/api/v1/home-safety/visits",
        headers=auth_headers,
        json={
            "elder_id": elder.id,
            "visit_type": "Wellness visit",
            "staff_name": "Nurse",
            "summary": "Forgot baseline",
            "checkin": {"overall": "normal", "mobility": "normal_for_them"},
        },
    )
    assert missing.status_code == 400
