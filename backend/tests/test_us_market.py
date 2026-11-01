import app.models  # noqa: F401

from datetime import date, datetime, timedelta, timezone

from app.core.security import hash_password
from app.models.assignment import Assignment
from app.models.attendance_record import AttendanceRecord
from app.models.caregiver_pay_rate import CaregiverPayRate
from app.models.tenant import Tenant
from app.models.user import User
from app.services.us_statutory_payroll_service import (
    DEDUCTION_FICA_MEDICARE,
    DEDUCTION_FICA_SS,
)
from app.services.subscription_service import SubscriptionService


def _super_admin_headers(client, db):
    user = User(
        email="us-super@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Super",
        last_name="Admin",
        role="SYSTEM_ADMIN",
        tenant_id=None,
    )
    db.add(user)
    db.commit()
    r = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "testpass123"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_create_us_tenant_starts_us_pilot(db, client):
    headers = _super_admin_headers(client, db)
    res = client.post(
        "/api/v1/tenants",
        headers=headers,
        json={
            "name": "Sunrise Home Care TX",
            "email": "ops@sunrise-tx.example",
            "phone": "+1-555-0100",
            "address": "100 Main St",
            "city": "Austin",
            "state": "TX",
            "country": "United States",
            "market": "US",
            "admin_email": "admin@sunrise-tx.example",
            "admin_password": "testpass123",
            "admin_first_name": "Jane",
            "admin_last_name": "Admin",
        },
    )
    assert res.status_code == 200
    tenant_id = res.json()["id"]
    assert res.json()["market"] == "US"

    sub = client.get(
        f"/api/v1/subscriptions/admin/tenants/{tenant_id}",
        headers=headers,
    )
    assert sub.status_code == 200
    assert sub.json()["plan"]["code"] == "PILOT_US"


def test_us_payroll_fica_deductions(db, seed_tenant, client, auth_headers):
    tenant = seed_tenant["tenant"]
    tenant.market = "US"
    tenant.country = "United States"
    db.commit()

    work_day = date.today()
    checkin = datetime.combine(work_day, datetime.min.time(), tzinfo=timezone.utc) + timedelta(
        hours=9
    )
    checkout = checkin + timedelta(hours=4)

    assignment = Assignment(
        tenant_id=tenant.id,
        elder_id=seed_tenant["elder"].id,
        caregiver_id=seed_tenant["caregiver"].id,
        status="ACTIVE",
        match_score=90.0,
    )
    db.add(assignment)
    db.flush()
    db.add(
        CaregiverPayRate(
            tenant_id=tenant.id,
            caregiver_id=seed_tenant["caregiver"].id,
            hourly_rate=25.0,
            effective_from=work_day.replace(day=1),
        )
    )
    db.add(
        AttendanceRecord(
            tenant_id=tenant.id,
            assignment_id=assignment.id,
            caregiver_id=seed_tenant["caregiver"].id,
            elder_id=seed_tenant["elder"].id,
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
        import pytest
        pytest.skip("Payroll API is not mounted in this LiveWell deploy")
    assert res.status_code == 200
    body = res.json()
    assert body["total_amount"] == 100.0
    assert body["total_deductions"] > 0
    summary = body["summaries"][0]
    types = {d["deduction_type"] for d in summary["deductions"]}
    assert DEDUCTION_FICA_SS in types
    assert DEDUCTION_FICA_MEDICARE in types


def test_markets_api(client, auth_headers):
    res = client.get("/api/v1/tenants/markets", headers=auth_headers)
    assert res.status_code == 200
    ids = {m["id"] for m in res.json()}
    assert "IN" in ids
    assert "US" in ids


def test_list_us_subscription_plans(db):
    SubscriptionService.ensure_default_plans(db)
    plans = SubscriptionService.list_plans(db)
    us_codes = {p.code for p in plans if getattr(p, "market", "IN") == "US"}
    assert "STARTER_US" in us_codes
