import pytest

from app.core.verticals import (
    DRIVER_SERVICES,
    HOME_HEALTHCARE,
    HOUSEKEEPING,
    SECURITY,
    has_feature,
    vertical_features,
)


@pytest.mark.parametrize(
    "vertical",
    [SECURITY, DRIVER_SERVICES, HOME_HEALTHCARE],
)
def test_placeholder_verticals_have_workforce_core_only(vertical):
    features = vertical_features(vertical)
    assert "caregiver_prospects" in features
    assert "elders" not in features
    assert "elder_matching" not in features
    assert "elder_billing" not in features
    assert "elder_prospects" not in features
    assert "monitoring" not in features
    assert "cleaning_properties" not in features
    assert "cleaning_crm" not in features
    assert "cleaning_price_book" not in features


def test_housekeeping_contract_has_cleaning_not_elder():
    """Core contract still defines HOUSEKEEPING for HousekeepingOps deploy."""
    features = vertical_features(HOUSEKEEPING)
    assert "cleaning_crm" in features
    assert "cleaning_price_book" in features
    assert "elders" not in features
    assert "monitoring" not in features


def test_cleaning_routes_not_mounted_on_elder_deploy(client, auth_headers):
    res = client.post(
        "/api/v1/cleaning/properties",
        headers=auth_headers,
        json={"elder_id": 1, "country_code": "IND"},
    )
    assert res.status_code == 404


@pytest.mark.parametrize(
    "vertical",
    [SECURITY, DRIVER_SERVICES, HOME_HEALTHCARE],
)
def test_placeholder_verticals_block_industry_apis(db, client, seed_tenant, vertical):
    seed_tenant["tenant"].vertical = vertical
    db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "manager@test.example", "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get("/api/v1/elders", headers=headers).status_code in (400, 403, 404)
    assert client.get("/api/v1/prospects/elders", headers=headers).status_code in (400, 403, 404)
    assert client.get("/api/v1/monitoring/summary", headers=headers).status_code in (400, 403, 404)
    assert client.get("/api/v1/billing/invoices", headers=headers).status_code in (400, 403, 404)


@pytest.mark.parametrize(
    "vertical",
    [SECURITY, DRIVER_SERVICES, HOME_HEALTHCARE],
)
def test_placeholder_verticals_allow_caregiver_recruitment(
    db, client, seed_tenant, vertical
):
    seed_tenant["tenant"].vertical = vertical
    db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "manager@test.example", "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    res = client.get("/api/v1/prospects/caregivers", headers=headers)
    assert res.status_code == 200
    assert has_feature(vertical, "caregiver_prospects")
