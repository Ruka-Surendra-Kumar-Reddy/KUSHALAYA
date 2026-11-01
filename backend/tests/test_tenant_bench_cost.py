def _login_headers(client, email: str) -> dict:
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "testpass123"},
    )
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_tenant_admin_updates_bench_cost(client, seed_tenant):
    admin_headers = _login_headers(client, "admin@test.example")
    res = client.patch(
        "/api/v1/tenants/me/branding",
        headers=admin_headers,
        json={"bench_cost_per_caregiver_month_inr": 22_000},
    )
    assert res.status_code == 200
    assert res.json()["bench_cost_per_caregiver_month_inr"] == 22_000

    manager_headers = _login_headers(client, "manager@test.example")
    exec_res = client.get(
        "/api/v1/executive/dashboard",
        headers=manager_headers,
    )
    if exec_res.status_code == 404:
        import pytest
        pytest.skip("Executive dashboard is not mounted in this LiveWell deploy")
    assert exec_res.status_code == 200
    body = exec_res.json()
    assert body["tenant_settings"]["bench_cost_per_caregiver_month_inr"] == 22_000
    assert (
        body["bench_intelligence"]["bench_cost_per_caregiver_month_inr"] == 22_000
    )


def test_care_manager_updates_bench_cost(client, seed_tenant):
    manager_headers = _login_headers(client, "manager@test.example")
    res = client.patch(
        "/api/v1/tenants/me/branding",
        headers=manager_headers,
        json={"bench_cost_per_caregiver_month_inr": 18_500},
    )
    assert res.status_code == 200
    assert res.json()["bench_cost_per_caregiver_month_inr"] == 18_500

    forbidden = client.patch(
        "/api/v1/tenants/me/branding",
        headers=manager_headers,
        json={"theme": "ocean", "bench_cost_per_caregiver_month_inr": 18_500},
    )
    assert forbidden.status_code == 400


def test_bench_cost_validation(client, seed_tenant):
    admin_headers = _login_headers(client, "admin@test.example")
    res = client.patch(
        "/api/v1/tenants/me/branding",
        headers=admin_headers,
        json={"bench_cost_per_caregiver_month_inr": 100},
    )
    assert res.status_code == 422
