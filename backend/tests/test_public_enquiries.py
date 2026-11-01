"""Public website enquiries — an unauthenticated write, so the guards matter."""

import pytest
from fastapi import HTTPException

from app.livewell.public_enquiry_service import (
    RATE_LIMIT_PER_HOUR,
    PublicEnquiryService,
)
from app.models.elder_prospect import ElderProspect


def _create(db, **over):
    payload = dict(
        name="Anita Rao",
        phone="+91 90000 00000",
        email=None,
        area="Madhapur, Hyderabad",
        services=["Nursing visits"],
        visit_frequency="2 a month",
        products=["Fixed grab bar"],
        notes="Mother had a fall last month.",
        kind="custom-plan",
    )
    payload.update(over)
    return PublicEnquiryService.create(db, **payload)


def test_enquiry_lands_in_the_pipeline_as_a_new_prospect(db, seed_tenant):
    row = _create(db)
    assert row.id
    assert row.stage == "NEW"
    assert row.tenant_id == seed_tenant["tenant"].id
    assert row.source == "website:custom-plan"


def test_selections_are_captured_in_the_notes(db, seed_tenant):
    row = _create(db)
    assert "Nursing visits" in row.notes
    assert "2 a month" in row.notes
    assert "Fixed grab bar" in row.notes
    assert "Madhapur" in row.notes
    assert "fall last month" in row.notes


def test_name_is_split_into_first_and_last(db, seed_tenant):
    row = _create(db, name="Anita Rao")
    assert row.first_name == "Anita"
    assert row.last_name == "Rao"


def test_single_word_name_still_works(db, seed_tenant):
    row = _create(db, name="Anita")
    assert row.first_name == "Anita"
    assert row.last_name == ""


def test_name_is_required(db, seed_tenant):
    with pytest.raises(HTTPException) as e:
        _create(db, name="   ")
    assert e.value.status_code == 422


def test_some_way_to_reply_is_required(db, seed_tenant):
    """An enquiry we cannot answer is worse than no enquiry."""
    with pytest.raises(HTTPException) as e:
        _create(db, phone=None, email=None)
    assert e.value.status_code == 422


def test_email_alone_is_enough(db, seed_tenant):
    row = _create(db, phone=None, email="anita@example.com")
    assert row.email == "anita@example.com"


def test_honeypot_rejects_bots(db, seed_tenant):
    with pytest.raises(HTTPException) as e:
        _create(db, honeypot="buy-cheap-pills")
    assert e.value.status_code == 422


def test_blank_honeypot_is_fine(db, seed_tenant):
    assert _create(db, honeypot="   ").id


def test_rate_limited_per_ip(db, seed_tenant):
    for _ in range(RATE_LIMIT_PER_HOUR):
        _create(db, source_ip="203.0.113.9")
    with pytest.raises(HTTPException) as e:
        _create(db, source_ip="203.0.113.9")
    assert e.value.status_code == 429


def test_rate_limit_is_per_ip_not_global(db, seed_tenant):
    """One bot must not be able to block every other visitor."""
    for _ in range(RATE_LIMIT_PER_HOUR):
        _create(db, source_ip="203.0.113.9")
    assert _create(db, source_ip="198.51.100.4").id


def test_oversized_input_is_truncated_not_rejected(db, seed_tenant):
    row = _create(
        db,
        name="A" * 500,
        area="B" * 2000,
        notes="C" * 20000,
        services=["S" * 500] * 100,
    )
    assert len(row.first_name) <= 100
    assert len(row.address or "") <= 500
    assert len(row.notes or "") <= 4000


def test_whitespace_is_trimmed(db, seed_tenant):
    row = _create(db, name="  Anita Rao  ", phone="  +91 90000 00000  ")
    assert row.first_name == "Anita"
    assert row.phone == "+91 90000 00000"


def test_endpoint_accepts_an_enquiry_without_auth(client, seed_tenant):
    res = client.post(
        "/api/v1/home-safety/enquiries",
        json={
            "name": "Ravi Kumar",
            "phone": "+91 98888 77777",
            "kind": "care-check",
            "services": ["Home safety assessment"],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert body["reference"].startswith("KA-")


def test_endpoint_never_echoes_stored_data(client, seed_tenant):
    """The response must not become a read channel for the pipeline."""
    res = client.post(
        "/api/v1/home-safety/enquiries",
        json={"name": "Ravi Kumar", "phone": "+91 98888 77777", "notes": "secret note"},
    )
    assert res.status_code == 200
    assert set(res.json()) == {"ok", "reference"}
    assert "secret note" not in res.text


def test_endpoint_rejects_missing_contact(client, seed_tenant):
    res = client.post("/api/v1/home-safety/enquiries", json={"name": "No Contact"})
    assert res.status_code == 422


def test_endpoint_rejects_honeypot(client, seed_tenant):
    res = client.post(
        "/api/v1/home-safety/enquiries",
        json={"name": "Bot", "phone": "123", "company": "spam"},
    )
    assert res.status_code == 422


def test_enquiries_are_visible_to_ops_as_prospects(db, seed_tenant):
    _create(db, name="Visible Person")
    found = (
        db.query(ElderProspect)
        .filter(ElderProspect.first_name == "Visible")
        .one_or_none()
    )
    assert found is not None
    assert found.stage == "NEW"


# --- Public stats for the marketing site ----------------------------------

def test_public_stats_never_errors_and_rounds_down(db, seed_tenant):
    """The www page calls this unauthenticated; it must answer even on a
    database without the optional tables, and never reveal exact counts."""
    from app.api.v1 import public_enquiries as mod

    mod._stats_cache["value"] = None
    result = mod.public_stats(db=db)
    for field in ("families", "visits", "assessments"):
        value = getattr(result, field)
        assert isinstance(value, int)
        assert value >= 0
        assert value % 5 == 0
    assert result.partners is None


def test_public_stats_is_cached(db, seed_tenant):
    from app.api.v1 import public_enquiries as mod

    mod._stats_cache["value"] = None
    first = mod.public_stats(db=db)
    assert mod.public_stats(db=db) is first


# --- Server-side contact validation (round-2 audit: junk leads) ---

@pytest.mark.parametrize("bad_phone", ["abcdefghij", "12345", "+91 12345 67890"])
def test_service_rejects_junk_phone(db, seed_tenant, bad_phone):
    with pytest.raises(HTTPException) as exc:
        _create(db, phone=bad_phone)
    assert exc.value.status_code == 422
    assert "10-digit" in exc.value.detail


def test_service_rejects_junk_email(db, seed_tenant):
    with pytest.raises(HTTPException) as exc:
        _create(db, phone=None, email="not-an-email")
    assert exc.value.status_code == 422
    assert "email" in exc.value.detail.lower()


def test_service_normalises_good_contact(db, seed_tenant):
    row = _create(db, phone="098765 43210", email=" Anita@Example.com ")
    assert row.phone == "+91 98765 43210"
    assert row.email == "anita@example.com"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "Phone Test", "phone": "abcdefghij"},
        {"name": "Phone Test", "phone": "12345"},
        {"name": "Mail Test", "email": "not-an-email"},
    ],
)
def test_endpoint_rejects_junk_contact(client, seed_tenant, payload):
    res = client.post("/api/v1/home-safety/enquiries", json=payload)
    assert res.status_code == 422


def _staff_headers(client):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "manager@test.example", "password": "testpass123"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.parametrize(
    "contact,needle",
    [
        ({"phone": "abcdefghij"}, "10-digit"),
        ({"phone": "12345"}, "10-digit"),
        ({"email": "not-an-email"}, "email"),
    ],
)
def test_staff_added_enquiry_rejects_junk(client, seed_tenant, contact, needle):
    res = client.post(
        "/api/v1/prospects/elders",
        headers=_staff_headers(client),
        json={"first_name": "Phone", "last_name": "Test", **contact},
    )
    assert res.status_code == 422
    assert needle in res.json()["detail"].lower() or needle in res.json()["detail"]


def test_staff_edit_rejects_junk_phone(client, seed_tenant):
    headers = _staff_headers(client)
    made = client.post(
        "/api/v1/prospects/elders",
        headers=headers,
        json={"first_name": "Good", "last_name": "Lead", "phone": "9876543210"},
    )
    assert made.status_code == 200, made.text
    assert made.json()["phone"] == "+91 98765 43210"
    res = client.patch(
        f"/api/v1/prospects/elders/{made.json()['id']}", headers=headers, json={"phone": "12345"}
    )
    assert res.status_code == 422
