"""Family portal multi-elder household access."""

from app.core.security import hash_password
from app.models.elder import Elder
from app.models.family_elder_link import FamilyElderLink
from app.models.user import User
from app.livewell.family_elder_access import ensure_family_elder_link


def _family_headers(client, db, seed_tenant, *, email="multi.family@test.example"):
    elders = db.query(Elder).filter(Elder.tenant_id == seed_tenant["tenant"].id).all()
    assert len(elders) >= 1
    primary = elders[0]
    user = User(
        email=email,
        password_hash=hash_password("testpass123"),
        first_name="Multi",
        last_name="Family",
        role="ELDER_PORTAL",
        tenant_id=primary.tenant_id,
        elder_id=primary.id,
    )
    db.add(user)
    db.flush()
    ensure_family_elder_link(db, user, primary)
    db.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    return headers, user, elders


def test_family_elders_list_and_switch(db, client, seed_tenant):
    headers, user, elders = _family_headers(client, db, seed_tenant)
    res = client.get("/api/v1/home-safety/family/elders", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["active_elder_id"] == elders[0].id
    assert len(data["elders"]) >= 1
    assert data["elders"][0]["is_active"] is True

    # Need a second elder in tenant for switch test
    if len(elders) < 2:
        second = Elder(
            tenant_id=elders[0].tenant_id,
            first_name="Second",
            last_name="Senior",
            status="ACTIVE",
        )
        db.add(second)
        db.flush()
        ensure_family_elder_link(db, user, second)
        db.commit()
        second_id = second.id
    else:
        second_id = elders[1].id
        ensure_family_elder_link(db, user, elders[1])
        db.commit()

    res2 = client.post(
        "/api/v1/home-safety/family/elders/active",
        headers=headers,
        json={"elder_id": second_id},
    )
    assert res2.status_code == 200
    body = res2.json()
    assert body["active_elder_id"] == second_id
    assert any(e["id"] == second_id and e["is_active"] for e in body["elders"])

    dash = client.get("/api/v1/home-safety/family/dashboard", headers=headers)
    assert dash.status_code == 200
    assert dash.json()["active_elder_id"] == second_id
    assert len(dash.json()["elders"]) >= 2


def test_staff_link_family_user(db, client, seed_tenant):
    admin = seed_tenant["admin"]
    login = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "testpass123"},
    )
    assert login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    headers, user, elders = _family_headers(
        client, db, seed_tenant, email="link.family@test.example"
    )
    del headers  # family token unused
    elder = elders[0]
    second = Elder(
        tenant_id=elder.tenant_id,
        first_name="Linked",
        last_name="Senior",
        status="ACTIVE",
    )
    db.add(second)
    db.commit()

    res = client.post(
        f"/api/v1/home-safety/care/elders/{second.id}/family-links",
        headers=admin_headers,
        json={"email": user.email, "set_active": False},
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert len(payload["elders"]) >= 2
    assert (
        db.query(FamilyElderLink)
        .filter(FamilyElderLink.user_id == user.id, FamilyElderLink.elder_id == second.id)
        .first()
    )


def test_staff_login_as_family(db, client, seed_tenant):
    admin = seed_tenant["admin"]
    login = client.post(
        "/api/v1/auth/login",
        json={"email": admin.email, "password": "testpass123"},
    )
    assert login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    _headers, user, elders = _family_headers(
        client, db, seed_tenant, email="impersonate.family@test.example"
    )
    elder = elders[0]
    res = client.post(
        f"/api/v1/elders/{elder.id}/login-as-family",
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["role"] == "ELDER_PORTAL"
    assert body["email"] == user.email
    assert body["elder_id"] == elder.id
    assert body["access_token"]
