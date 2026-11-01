def _login_headers(client, email: str) -> dict:
    res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "testpass123"},
    )
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_field_schema_demand_supply_aliases(client, seed_tenant):
    headers = _login_headers(client, "admin@test.example")
    res = client.patch(
        "/api/v1/tenants/me/field-schemas",
        headers=headers,
        json={
            "demand_fields": [
                {
                    "key": "floor_level",
                    "label": "Floor level",
                    "type": "text",
                }
            ],
            "supply_fields": [
                {
                    "key": "vehicle_type",
                    "label": "Vehicle type",
                    "type": "text",
                }
            ],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["demand_fields"][0]["key"] == "floor_level"
    assert body["elder_fields"][0]["key"] == "floor_level"
    assert body["supply_fields"][0]["key"] == "vehicle_type"
    assert body["caregiver_fields"][0]["key"] == "vehicle_type"


def test_matching_returns_vertical(client, auth_headers, seed_tenant):
    elder_id = seed_tenant["elder"].id
    res = client.post(
        "/api/v1/matching/recommend",
        headers=auth_headers,
        json={"elder_id": elder_id, "limit": 5},
    )
    if res.status_code == 404:
        import pytest
        pytest.skip("Matching API is not mounted in this LiveWell deploy")
    assert res.status_code == 200
    assert res.json()["vertical"] == "ELDER_CARE"


def test_copilot_uses_vertical_pack(client, auth_headers, seed_tenant):
    from unittest.mock import patch

    with patch(
        "app.services.azure_openai_service.is_configured",
        return_value=True,
    ), patch(
        "app.services.azure_openai_service.chat_completion",
        return_value="OK",
    ) as mock_chat:
        res = client.post(
            "/api/v1/copilot/ask",
            headers=auth_headers,
            json={"question": "What is our bench utilization?"},
        )
    if res.status_code == 404:
        import pytest
        pytest.skip("Copilot API is not mounted in this LiveWell deploy")
    assert res.status_code == 200
    assert res.json()["vertical"] == "ELDER_CARE"
    system_msg = mock_chat.call_args[0][0][0]["content"]
    assert "WorkforceOS" in system_msg
