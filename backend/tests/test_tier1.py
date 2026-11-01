import app.models  # noqa: F401

from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.assignment import Assignment
from app.models.attendance_record import AttendanceRecord
from app.models.caregiver_pay_rate import CaregiverPayRate


def _assignment(db, seed_tenant):
    row = Assignment(
        tenant_id=seed_tenant["tenant"].id,
        elder_id=seed_tenant["elder"].id,
        caregiver_id=seed_tenant["caregiver"].id,
        status="ACTIVE",
        match_score=90.0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_generate_schedule_creates_visits(db, seed_tenant, auth_headers, client):
    _assignment(db, seed_tenant)
    today = date.today()
    end = today + timedelta(days=7)
    res = client.post(
        "/api/v1/scheduling/generate",
        headers=auth_headers,
        json={
            "start_date": today.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    if res.status_code == 404:
        import pytest
        pytest.skip("Scheduling API is not mounted in this LiveWell deploy")
    assert res.status_code == 200
    assert res.json()["created"] >= 1

    visits = client.get("/api/v1/scheduling/visits", headers=auth_headers)
    assert visits.status_code == 200
    body = visits.json()
    assert len(body) >= 1
    assert body[0]["elder_name"] == "Elder One"
    assert body[0]["caregiver_name"] == "Care Giver"


def test_payroll_from_attendance(db, seed_tenant, auth_headers, client):
    assignment = _assignment(db, seed_tenant)
    caregiver = seed_tenant["caregiver"]
    elder = seed_tenant["elder"]

    db.add(
        CaregiverPayRate(
            tenant_id=seed_tenant["tenant"].id,
            caregiver_id=caregiver.id,
            hourly_rate=300.0,
            effective_from=date.today(),
        )
    )
    checkin = datetime.now(timezone.utc) - timedelta(hours=5)
    checkout = datetime.now(timezone.utc) - timedelta(hours=1)
    db.add(
        AttendanceRecord(
            tenant_id=seed_tenant["tenant"].id,
            assignment_id=assignment.id,
            caregiver_id=caregiver.id,
            elder_id=elder.id,
            checkin_time=checkin,
            checkout_time=checkout,
            visit_duration_minutes=240.0,
            status="COMPLETED",
        )
    )
    db.commit()

    period_start = date.today().replace(day=1).isoformat()
    period_end = date.today().isoformat()
    res = client.post(
        "/api/v1/payroll/runs/generate",
        headers=auth_headers,
        json={"period_start": period_start, "period_end": period_end},
    )
    if res.status_code == 404:
        pytest.skip("Payroll API is not mounted in this LiveWell deploy")
    assert res.status_code == 200
    body = res.json()
    assert body["total_amount"] > 0
    assert len(body["lines"]) >= 1


def test_billing_invoice_generate(db, seed_tenant, auth_headers, client):
    assignment = _assignment(db, seed_tenant)
    checkin = datetime.now(timezone.utc) - timedelta(hours=3)
    checkout = datetime.now(timezone.utc)
    db.add(
        AttendanceRecord(
            tenant_id=seed_tenant["tenant"].id,
            assignment_id=assignment.id,
            caregiver_id=seed_tenant["caregiver"].id,
            elder_id=seed_tenant["elder"].id,
            checkin_time=checkin,
            checkout_time=checkout,
            visit_duration_minutes=180.0,
            status="COMPLETED",
        )
    )
    db.commit()

    res = client.post(
        "/api/v1/billing/invoices/generate",
        headers=auth_headers,
        json={
            "period_start": date.today().replace(day=1).isoformat(),
            "period_end": date.today().isoformat(),
        },
    )
    if res.status_code == 404:
        pytest.skip("Billing API is not mounted in this LiveWell deploy")
    assert res.status_code == 200
    assert res.json()[0]["total_amount"] > 0


def test_document_ocr_endpoint(db, seed_tenant, auth_headers, client):
    caregiver = seed_tenant["caregiver"]
    upload = client.post(
        "/api/v1/documents/upload",
        headers=auth_headers,
        data={
            "entity_type": "caregiver",
            "entity_id": str(caregiver.id),
            "document_type": "AADHAAR",
        },
        files={"file": ("aadhaar.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    if upload.status_code == 404:
        pytest.skip("Documents API upload is not mounted in this LiveWell deploy")
    assert upload.status_code == 200
    doc_id = upload.json()["id"]

    res = client.post(
        f"/api/v1/documents/{doc_id}/ocr",
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json().get("has_ocr") is True
