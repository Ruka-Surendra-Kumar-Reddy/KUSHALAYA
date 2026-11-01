def test_login_success(client, seed_tenant):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "manager@test.example", "password": "testpass123"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "manager@test.example"
    assert data["role"] == "CARE_MANAGER"
    assert "access_token" in data


def test_login_invalid_password(client, seed_tenant):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "manager@test.example", "password": "wrong"},
    )
    assert res.status_code == 400


def test_me_requires_auth(client):
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 403


def test_me_with_token(client, auth_headers):
    res = client.get("/api/v1/auth/me", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["email"] == "manager@test.example"


def test_login_unknown_email(client, seed_tenant):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.example", "password": "testpass123"},
    )
    assert res.status_code == 400


def test_admin_login_and_me(client, seed_tenant):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.example", "password": "testpass123"},
    )
    assert res.status_code == 200
    token = res.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "TENANT_ADMIN"


def test_refresh_rejects_garbage_token(client, seed_tenant):
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-jwt"})
    assert res.status_code in (400, 401, 403)


def test_register_tenant_rejects_housekeeping_vertical(client):
    res = client.post(
        "/api/v1/auth/register-tenant",
        json={
            "email": "owner@cleaning.example",
            "password": "testpass123",
            "first_name": "Alex",
            "last_name": "Owner",
            "tenant_name": "Sparkle Clean Co",
            "tenant_email": "ops@cleaning.example",
            "phone": "555-0100",
            "address": "1 Main St",
            "city": "Austin",
            "state": "TX",
            "country": "United States",
            "market": "US",
            "vertical": "HOUSEKEEPING",
        },
    )
    assert res.status_code == 400
    assert "LIVEWELL360" in res.json()["detail"]


def test_login_email_is_case_and_whitespace_insensitive(client, seed_tenant):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "  Manager@Test.Example ", "password": "testpass123"},
    )
    assert res.status_code == 200
    assert res.json()["email"] == "manager@test.example"


def test_login_malformed_email_is_a_plain_400(client, seed_tenant):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "testpass123"},
    )
    assert res.status_code == 400
