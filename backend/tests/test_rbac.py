import pytest


def test_viewer_cannot_create_elder(client, seed_tenant):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "viewer@test.example", "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    res = client.post(
        "/api/v1/elders",
        headers=headers,
        json={"first_name": "X", "last_name": "Y"},
    )
    assert res.status_code == 403


def test_manager_can_list_elders(client, auth_headers):
    res = client.get("/api/v1/elders", headers=auth_headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1


def test_matching_config_readable(client, auth_headers):
    res = client.get("/api/v1/matching/config", headers=auth_headers)
    if res.status_code == 404:
        pytest.skip("Matching API is not mounted in this LiveWell deploy")
    assert res.status_code == 200
    assert res.json()["algorithm_version"] == "rules-v1-elder-care"
    assert "skill" in res.json()["weights"]
