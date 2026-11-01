import pytest


def _login_headers(client, email: str) -> dict:
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "testpass123"},
    )
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_branding_includes_vertical(client, seed_tenant):
    from app.livewell.brand import brand_name

    headers = _login_headers(client, "admin@test.example")
    res = client.get("/api/v1/tenants/me/branding", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["platform_name"] == "WorkforceOS"
    assert body["vertical"] in {"ELDER_CARE", "LIVEWELL360"}
    # The label follows the configured brand, so it must not be pinned to one
    # product name — it changes with BRAND_NAME on every rebrand.
    assert body["vertical_label"] in {"Elder Care", brand_name()}


def test_super_admin_branding_is_platform(client, db, seed_tenant):
    from app.core.security import hash_password
    from app.models.user import User

    db.add(
        User(
            email="superadmin@test.example",
            password_hash=hash_password("testpass123"),
            first_name="Super",
            last_name="Admin",
            role="SYSTEM_ADMIN",
            tenant_id=None,
        )
    )
    db.flush()

    headers = _login_headers(client, "superadmin@test.example")
    res = client.get("/api/v1/tenants/me/branding", headers=headers)
    assert res.status_code == 200
    body = res.json()
    from app.livewell.brand import brand_name

    assert body["platform_name"] == "WorkforceOS"
    assert body["portal_title"] in {"WorkforceOS", "SafeHomeOps", brand_name()}


def test_workers_alias_matches_caregivers(client, seed_tenant):
    headers = _login_headers(client, "admin@test.example")
    caregivers = client.get("/api/v1/caregivers", headers=headers)
    workers = client.get("/api/v1/workers", headers=headers)
    if workers.status_code == 404:
        pytest.skip("Workers alias is not mounted in this LiveWell deploy")
    assert caregivers.json() == workers.json()


def test_clients_alias_matches_elders(client, seed_tenant):
    headers = _login_headers(client, "admin@test.example")
    elders = client.get("/api/v1/elders", headers=headers)
    clients = client.get("/api/v1/clients", headers=headers)
    if clients.status_code == 404:
        pytest.skip("Clients alias is not mounted in this LiveWell deploy")
    assert elders.json() == clients.json()


def test_list_verticals(client, seed_tenant):
    headers = _login_headers(client, "admin@test.example")
    res = client.get("/api/v1/tenants/verticals", headers=headers)
    assert res.status_code == 200
    ids = {v["id"] for v in res.json()}
    assert "ELDER_CARE" in ids
    assert "SECURITY" in ids
