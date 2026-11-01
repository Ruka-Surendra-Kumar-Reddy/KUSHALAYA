def test_health_live(client):
    res = client.get("/health/live")
    assert res.status_code == 200
    assert res.json()["status"] == "alive"


def test_health_ready(client):
    res = client.get("/health/ready")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "healthy"
    assert body["checks"]["database"]["ok"] is True
    assert body["checks"]["storage"]["ok"] is True


def test_health_alias(client):
    res = client.get("/health")
    assert res.status_code == 200


def test_health_reports_release(client):
    from app.release import RELEASE_ID

    assert client.get("/health").json()["release"] == RELEASE_ID
    assert client.get("/health/live").json()["release"] == RELEASE_ID


def test_db_test_open_outside_production(client):
    res = client.get("/db-test")
    assert res.status_code == 200
    assert res.json()["status"] == "connected"


def test_db_test_requires_admin_in_production(client, seed_tenant, auth_headers, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")

    # No token at all.
    assert client.get("/db-test").status_code == 401
    # Garbage token.
    assert client.get("/db-test", headers={"Authorization": "Bearer nope"}).status_code == 401
    # A signed-in non-admin (auth_headers is the CARE_MANAGER).
    assert client.get("/db-test", headers=auth_headers).status_code == 403

    admin = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.example", "password": "testpass123"},
    ).json()["access_token"]
    res = client.get("/db-test", headers={"Authorization": f"Bearer {admin}"})
    assert res.status_code == 200
    assert res.json()["status"] == "connected"
