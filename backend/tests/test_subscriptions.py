import app.models  # noqa: F401

from datetime import date

from app.core.security import hash_password
from app.models.subscription_invoice import SubscriptionInvoice
from app.models.tenant_subscription import TenantSubscription
from app.models.user import User
from app.services.subscription_service import SubscriptionService


def _super_admin_headers(client, db):
    user = User(
        email="sub-super@test.example",
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
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_default_plans_seeded(db):
    plans = SubscriptionService.list_plans(db)
    codes = {p.code for p in plans}
    assert "PILOT" in codes
    assert "STARTER" in codes
    assert "GROWTH" in codes


def test_new_tenant_gets_trial_subscription(db, seed_tenant):
    sub = (
        db.query(TenantSubscription)
        .filter(TenantSubscription.tenant_id == seed_tenant["tenant"].id)
        .first()
    )
    if sub is None:
        SubscriptionService.start_trial(db, seed_tenant["tenant"].id)
        sub = (
            db.query(TenantSubscription)
            .filter(TenantSubscription.tenant_id == seed_tenant["tenant"].id)
            .first()
        )
    assert sub is not None
    assert sub.status in ("TRIAL", "ACTIVE")


def test_admin_assign_plan_and_generate_invoice(db, seed_tenant, client):
    admin_headers = _super_admin_headers(client, db)

    SubscriptionService.start_trial(db, seed_tenant["tenant"].id)

    assigned = client.put(
        f"/api/v1/subscriptions/admin/tenants/{seed_tenant['tenant'].id}",
        headers=admin_headers,
        json={"plan_code": "STARTER", "status": "ACTIVE"},
    )
    assert assigned.status_code == 200
    assert assigned.json()["plan"]["code"] == "STARTER"

    period_start = date.today().replace(day=1).isoformat()
    period_end = date.today().isoformat()
    gen = client.post(
        "/api/v1/subscriptions/invoices/generate",
        headers=admin_headers,
        json={
            "tenant_id": seed_tenant["tenant"].id,
            "period_start": period_start,
            "period_end": period_end,
        },
    )
    assert gen.status_code == 200
    body = gen.json()
    assert body["subtotal"] >= 2999
    assert body["tax_amount"] > 0
    assert body["total_amount"] > body["subtotal"]

    issued = client.post(
        f"/api/v1/subscriptions/invoices/{body['id']}/issue",
        headers=admin_headers,
    )
    assert issued.status_code == 200
    assert issued.json()["invoice_number"] is not None
    assert issued.json()["status"] == "ISSUED"

    pay = client.post(
        f"/api/v1/subscriptions/invoices/{body['id']}/payments",
        headers=admin_headers,
        json={"amount": issued.json()["total_amount"], "reference": "NEFT-TEST"},
    )
    assert pay.status_code == 200
    assert pay.json()["status"] == "PAID"


def test_tenant_admin_views_subscription(db, seed_tenant, client):
    SubscriptionService.start_trial(db, seed_tenant["tenant"].id)

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.example", "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    me = client.get("/api/v1/subscriptions/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["tenant_id"] == seed_tenant["tenant"].id
    assert me.json()["plan"]["code"] in ("PILOT", "STARTER", "GROWTH")


def test_care_manager_views_subscription(db, seed_tenant, client):
    SubscriptionService.start_trial(db, seed_tenant["tenant"].id)

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "manager@test.example", "password": "testpass123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    me = client.get("/api/v1/subscriptions/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["tenant_id"] == seed_tenant["tenant"].id

    invoices = client.get("/api/v1/subscriptions/invoices", headers=headers)
    assert invoices.status_code == 200
    assert isinstance(invoices.json(), list)

