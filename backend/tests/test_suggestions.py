"""Suggestions: risky answers point to the products that fix them."""
from tests.assess_client import confirm_client


from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.models.user import User


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_field_assessment_suggests_grab_bar_and_family_sees_it(client, db, seed_tenant, auth_headers):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    db.add(
        User(
            email="sugg.cg@test.example",
            password_hash=hash_password("testpass123"),
            first_name="S",
            last_name="CG",
            role="CAREGIVER",
            tenant_id=cg.tenant_id,
            caregiver_id=cg.id,
        )
    )
    db.add(
        User(
            email="sugg.fam@test.example",
            password_hash=hash_password("testpass123"),
            first_name="F",
            last_name="Am",
            role="ELDER_PORTAL",
            tenant_id=elder.tenant_id,
            elder_id=elder.id,
        )
    )
    db.commit()
    when = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    job = client.post(
        "/api/v1/jobs",
        json={"elder_id": elder.id, "kind": "assessment", "scheduled_at": when, "caregiver_id": cg.id},
        headers=auth_headers,
    ).json()
    field = _login(client, "sugg.cg@test.example")
    client.post(f"/api/v1/caregiver-portal/jobs/{job['id']}/status", json={"latitude": 17.4, "longitude": 78.4, "status": "checked_in"}, headers=field)
    form = client.get(f"/api/v1/caregiver-portal/jobs/{job['id']}/assessment", headers=field).json()
    items = {i["id"]: i["label"] for c in form["categories"] for i in c["items"]}
    grab = next(k for k, v in items.items() if "grab bar" in v.lower())
    ratings = {k: "excellent" for k in items}
    ratings[grab] = "unsafe"

    client.put(f"/api/v1/caregiver-portal/jobs/{job['id']}/assessment", json={"ratings": ratings}, headers=field)
    mine = client.get(f"/api/v1/caregiver-portal/jobs/{job['id']}/suggestions", headers=field).json()
    assert any("grab bar" in s["name"].lower() and s["priority"] == "high" for s in mine)
    assert all("cost_paise" not in s for s in mine)

    confirm_client(client, field, job["id"], portal=True)
    client.put(
        f"/api/v1/caregiver-portal/jobs/{job['id']}/assessment", json={"ratings": ratings, "complete": True, "latitude": 17.44, "longitude": 78.35}, headers=field
    )
    staff = client.get(f"/api/v1/suggestions?elder_id={elder.id}", headers=auth_headers).json()
    assert staff["assessment_status"] == "completed"
    assert any("grab bar" in s["name"].lower() for s in staff["items"])

    fam = client.get("/api/v1/home-safety/family/suggestions", headers=_login(client, "sugg.fam@test.example"))
    assert fam.status_code == 200, fam.text
    assert any("grab bar" in s["name"].lower() for s in fam.json()["items"])
    assert "cost" not in fam.text and "margin" not in fam.text


def test_product_fixes_listing(client, seed_tenant, auth_headers):
    res = client.get("/api/v1/products/fixes", headers=auth_headers).json()
    assert len(res["questions"]) > 20
    assert any(v["ids"] for v in res["fixes"].values())


def test_caregiver_room_photo_kept_on_assessment(client, db, seed_tenant, auth_headers):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    db.add(
        User(
            email="photo.cg@test.example",
            password_hash=hash_password("testpass123"),
            first_name="P",
            last_name="CG",
            role="CAREGIVER",
            tenant_id=cg.tenant_id,
            caregiver_id=cg.id,
        )
    )
    db.commit()
    when = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    job = client.post(
        "/api/v1/jobs",
        json={"elder_id": elder.id, "kind": "assessment", "scheduled_at": when, "caregiver_id": cg.id},
        headers=auth_headers,
    ).json()
    field = _login(client, "photo.cg@test.example")
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    res = client.post(
        f"/api/v1/caregiver-portal/jobs/{job['id']}/photos",
        files={"file": ("bath.png", png, "image/png")},
        data={"room_type": "bathroom"},
        headers=field,
    )
    assert res.status_code == 200, res.text
    client.put(f"/api/v1/caregiver-portal/jobs/{job['id']}/assessment", json={"ratings": {}}, headers=field)
    staff = client.get(f"/api/v1/suggestions?elder_id={elder.id}", headers=auth_headers).json()
    assert staff["photos"] and staff["photos"][0]["room_type"] == "bathroom"
