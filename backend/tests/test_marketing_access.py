"""Marketing logins: Blog without being an owner, all customers readable, nothing else writable."""

from app.models.user import User


def _marketing(client, admin_headers):
    res = client.post("/api/v1/users/invite", headers=admin_headers, json={
        "email": "shruti@test.example", "password": "testpass123", "first_name": "Shruti", "last_name": "G",
        "role": "MARKETING", "tenant_id": client.get("/api/v1/auth/me", headers=admin_headers).json()["tenant_id"],
    })
    assert res.status_code in (200, 201), res.text
    login = client.post("/api/v1/auth/login", json={"email": "shruti@test.example", "password": "testpass123"})
    assert login.status_code == 200, login.text
    assert login.json()["access_profile"] == "marketing" and login.json()["role"] == "CARE_MANAGER"
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_can_write_a_blog_post_and_vendor(client, seed_tenant, admin_headers):
    h = _marketing(client, admin_headers)
    assert client.get("/api/v1/blog/posts", headers=h).status_code == 200
    assert client.post("/api/v1/blog/posts", headers=h, json={"title": "From marketing"}).status_code == 201
    vendor = client.post("/api/v1/vendors", headers=h, json={"company_name": "Sri Sai", "phone1": "9876543210"})
    assert vendor.status_code == 201, vendor.text


def test_care_manager_still_has_no_blog(client, seed_tenant, auth_headers):
    assert client.get("/api/v1/blog/posts", headers=auth_headers).status_code == 403


def test_cannot_change_customers_or_team(client, seed_tenant, admin_headers):
    h = _marketing(client, admin_headers)
    assert client.post("/api/v1/team/clients", headers=h, json={"first_name": "A", "last_name": "B"}).status_code == 403
    assert client.post("/api/v1/users/invite", headers=h, json={}).status_code == 403
    assert client.get("/api/v1/staff-documents/staff/1", headers=h).status_code == 403


def test_role_change_sets_and_clears_marketing(client, db, seed_tenant, admin_headers):
    _marketing(client, admin_headers)
    row = db.query(User).filter(User.email == "shruti@test.example").one()
    res = client.patch(f"/api/v1/users/{row.id}", headers=admin_headers, json={"role": "VIEWER"})
    assert res.status_code == 200 and res.json()["access_profile"] is None
    res = client.patch(f"/api/v1/users/{row.id}", headers=admin_headers, json={"role": "MARKETING"})
    assert res.status_code == 200 and res.json()["access_profile"] == "marketing"
    assert res.json()["role"] == "CARE_MANAGER"


def test_invite_without_password_sends_setup_link(client, seed_tenant, admin_headers, monkeypatch):
    sent = []
    monkeypatch.setattr("app.services.account_setup.send_account_setup", lambda db, row, **kw: sent.append((row.email, kw.get("phone"))))
    tenant_id = client.get("/api/v1/auth/me", headers=admin_headers).json()["tenant_id"]
    res = client.post("/api/v1/users/invite", headers=admin_headers, json={
        "email": "new@test.example", "password": None, "first_name": "New", "last_name": "Staff",
        "role": "MARKETING", "tenant_id": tenant_id, "phone": "8019550561",
    })
    assert res.status_code in (200, 201), res.text
    assert sent == [("new@test.example", "8019550561")]
