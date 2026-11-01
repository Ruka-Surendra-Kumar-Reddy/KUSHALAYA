"""Ops client profile + visit location / staff feedback / photo attach."""

from app.livewell.visit_service import (
    _haversine_m,
    _normalize_location,
    _normalize_staff_feedback,
    normalize_visit,
    visit_to_family_response,
)


def test_location_is_validated_and_rounded():
    assert _normalize_location(None) is None
    assert _normalize_location({"lat": "x", "lng": 1}) is None
    assert _normalize_location({"lat": 91, "lng": 0}) is None
    loc = _normalize_location({"lat": 17.4123456789, "lng": 78.4481234567, "accuracy_m": "12.7"})
    assert loc["lat"] == 17.412346 and loc["lng"] == 78.448123
    assert loc["accuracy_m"] == 12 and loc["captured_at"]


def test_haversine_is_roughly_right():
    # ~111 km per degree of latitude
    assert 110_000 < _haversine_m(17.0, 78.0, 18.0, 78.0) < 112_500
    assert _haversine_m(17.4, 78.4, 17.4, 78.4) == 0


def test_staff_feedback_is_clamped():
    assert _normalize_staff_feedback({"rating": "nope"}) is None
    fb = _normalize_staff_feedback({"rating": 9, "comment": " ok ", "by_name": "Priya"})
    assert fb["rating"] == 5 and fb["comment"] == "ok" and fb["by_name"] == "Priya"


def test_families_never_see_staff_feedback_or_location():
    visit = normalize_visit(
        {
            "summary": "s",
            "photo_ids": [7],
            "location": {"lat": 17.4, "lng": 78.4},
            "staff_feedback": {"rating": 2, "comment": "family was rude"},
        }
    )
    family = visit_to_family_response(visit, tenant_id=1)
    assert family["staff_feedback"] is None and family["location"] is None
    assert family["photo_urls"] == ["/api/v1/home-safety/family/photos/7/image"]
    staff = visit_to_family_response(visit, tenant_id=1, staff=True)
    assert staff["staff_feedback"]["rating"] == 2
    assert staff["location"]["lat"] == 17.4
    assert staff["photo_urls"] == ["/api/v1/home-safety/photos/7/image"]


def test_visit_location_feedback_and_profile_end_to_end(db, client, seed_tenant, auth_headers):
    from app.models.elder import Elder
    from app.models.elder_location import ElderLocation

    tenant_id = seed_tenant["tenant"].id
    elder = Elder(
        tenant_id=tenant_id,
        first_name="Profile",
        last_name="Client",
        status="ACTIVE",
        manager_user_id=seed_tenant["manager"].id,
    )
    db.add(elder)
    db.commit()
    db.refresh(elder)
    db.add(
        ElderLocation(
            tenant_id=tenant_id, elder_id=elder.id, latitude=17.4000, longitude=78.4000, radius_meters=100
        )
    )
    db.commit()

    created = client.post(
        "/api/v1/home-safety/visits",
        headers=auth_headers,
        json={
            "elder_id": elder.id,
            "summary": "first visit",
            "status": "completed",
            "baseline": {"typical_mobility": "walks unaided"},
            "location": {"lat": 17.4003, "lng": 78.4002, "accuracy_m": 15},
        },
    )
    assert created.status_code == 200, created.text
    visit = created.json()
    assert visit["location"]["at_home"] is True
    assert visit["location"]["distance_from_home_m"] < 100
    assert visit["staff_feedback"] is None

    base = f"/api/v1/home-safety/visits/{elder.id}/{visit['id']}"
    fb = client.post(f"{base}/staff-feedback", headers=auth_headers, json={"rating": 4, "comment": "smooth"})
    assert fb.status_code == 200, fb.text
    assert fb.json()["staff_feedback"]["rating"] == 4

    # a photo that belongs to nobody must be refused
    bad = client.post(f"{base}/photos", headers=auth_headers, json={"photo_ids": [999999]})
    assert bad.status_code == 400

    profile = client.get(f"/api/v1/home-safety/clients/{elder.id}/profile", headers=auth_headers)
    assert profile.status_code == 200, profile.text
    body = profile.json()
    assert body["person"]["first_name"] == "Profile"
    assert len(body["visits"]) == 1
    assert body["feedback"]["staff_average"] == 4.0
    assert body["wallet"]["balance_minor"] == 0
    for key in ("family", "receipts", "service_requests", "incidents", "devices", "documents"):
        assert isinstance(body[key], list)

    assert client.get("/api/v1/home-safety/clients/987654/profile", headers=auth_headers).status_code == 404


def test_home_location_can_be_set_and_is_in_the_profile(db, client, seed_tenant, auth_headers):
    from app.models.elder import Elder

    elder = Elder(
        tenant_id=seed_tenant["tenant"].id,
        first_name="Home",
        last_name="Pin",
        status="ACTIVE",
        manager_user_id=seed_tenant["manager"].id,
    )
    db.add(elder)
    db.commit()
    db.refresh(elder)
    base = f"/api/v1/home-safety/clients/{elder.id}"
    assert client.get(f"{base}/profile", headers=auth_headers).json()["home_location"] is None
    saved = client.put(
        f"{base}/home-location", headers=auth_headers, json={"lat": 17.41234567, "lng": 78.4, "radius_m": 150}
    )
    assert saved.status_code == 200, saved.text
    assert saved.json() == {"lat": 17.412346, "lng": 78.4, "radius_m": 150}
    # second save updates the same row (elder_id is unique)
    again = client.put(f"{base}/home-location", headers=auth_headers, json={"lat": 17.5, "lng": 78.5})
    assert again.json()["radius_m"] == 100
    assert client.get(f"{base}/profile", headers=auth_headers).json()["home_location"]["lat"] == 17.5
    assert client.put(f"{base}/home-location", headers=auth_headers, json={"lat": 99, "lng": 0}).status_code == 422
