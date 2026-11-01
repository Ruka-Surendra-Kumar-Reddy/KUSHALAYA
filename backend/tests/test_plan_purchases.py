"""Website "Buy now" (Razorpay) and coupons on customer plans (30 Oct 2026)."""

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.livewell import plan_purchase_service as svc
from app.livewell.sales_pipeline import coupon_discount_paise
from app.models.commerce import Coupon
from app.models.customer_plan import CustomerPlan
from app.models.elder_prospect import ElderProspect
from app.models.pipeline_activity import PipelineActivity
from app.models.plan_purchase import PlanPurchase

BASE = "/api/v1/home-safety/plan-purchases"
WEBHOOK = "/api/v1/home-safety/family/wallet/webhook"


@pytest.fixture(autouse=True)
def _fresh_limits():
    from app.api.v1 import plan_purchases

    plan_purchases._quote_hits.clear()
    yield


@pytest.fixture
def coupons(db, seed_tenant):
    tid = seed_tenant["tenant"].id if isinstance(seed_tenant, dict) else seed_tenant.id
    rows = [
        Coupon(tenant_id=tid, code="PAYNOW3", kind="percent", value=300, used_count=0, active=True),
        Coupon(tenant_id=tid, code="PAYNOW5", kind="percent", value=500, used_count=0, active=True),
        Coupon(tenant_id=tid, code="FLAT1000", kind="amount", value=1000_00, used_count=0, active=True),
        Coupon(tenant_id=tid, code="OLD", kind="percent", value=500, used_count=0, active=True,
               expires_at=datetime.now(timezone.utc) - timedelta(days=1)),
        Coupon(tenant_id=tid, code="OFF", kind="percent", value=500, used_count=0, active=False),
        Coupon(tenant_id=tid, code="FULL", kind="percent", value=500, used_count=2, max_uses=2, active=True),
    ]
    db.add_all(rows)
    db.commit()
    return {c.code: c for c in rows}


def _buy(client, **over):
    body = {
        "plan_id": "privilege", "billing_cycle": "yearly", "name": "Ravi Kumar",
        "phone": "9876512345", "email": "ravi@example.com", "accept_terms": True,
    }
    body.update(over)
    return client.post(BASE, json=body)


def _coupon(db, code):
    db.expire_all()
    return db.query(Coupon).filter(Coupon.code == code).one()


# --- price ------------------------------------------------------------------


def test_discount_maths_in_paise():
    assert coupon_discount_paise(1_25_000_00, "percent", 300) == 3_750_00
    assert coupon_discount_paise(1_25_000_00, "percent", 500) == 6_250_00
    assert coupon_discount_paise(9_900_00, "percent", 300) == 297_00
    assert coupon_discount_paise(333, "percent", 300) == 9  # floored, never a fraction of a paisa
    assert coupon_discount_paise(5_000_00, "amount", 1000_00) == 1000_00
    assert coupon_discount_paise(500_00, "amount", 1000_00) == 500_00  # never below zero


def test_quote(client, coupons):
    r = client.post(f"{BASE}/quote", json={"plan_id": "privilege", "billing_cycle": "yearly"})
    assert r.status_code == 200, r.text
    assert r.json()["amount_paise"] == 1_25_000_00 and r.json()["coupon_code"] is None
    r = client.post(f"{BASE}/quote", json={"plan_id": "privilege", "billing_cycle": "monthly", "coupon_code": " paynow5 "})
    assert r.json() == {
        "plan_id": "privilege", "plan_name": "KushAlaya Privilege", "billing_cycle": "monthly",
        "list_paise": 13_500_00, "discount_paise": 675_00, "amount_paise": 12_825_00, "coupon_code": "PAYNOW5",
    }
    r = client.post(f"{BASE}/quote", json={"plan_id": "assurance", "billing_cycle": "yearly", "coupon_code": "FLAT1000"})
    assert r.json()["amount_paise"] == 54_000_00


@pytest.mark.parametrize("code,msg", [("OLD", "expired"), ("OFF", "not found"), ("FULL", "used up"), ("NOPE", "not found")])
def test_bad_coupons_rejected(client, coupons, code, msg):
    r = client.post(f"{BASE}/quote", json={"plan_id": "privilege", "billing_cycle": "yearly", "coupon_code": code})
    assert r.status_code == 400 and msg in r.json()["detail"].lower()
    assert _buy(client, coupon_code=code).status_code == 400


@pytest.mark.parametrize("plan,cycle", [("gold", "yearly"), ("privilege", "weekly"), ("", "")])
def test_wrong_plan_or_cycle(client, db, coupons, plan, cycle):
    assert _buy(client, plan_id=plan, billing_cycle=cycle).status_code == 422
    assert db.query(PlanPurchase).count() == 0 and db.query(ElderProspect).count() == 0


def test_needs_contact_and_terms(client, coupons):
    assert _buy(client, accept_terms=False).status_code == 422
    assert _buy(client, phone="").status_code == 422
    assert _buy(client, email="").status_code == 422
    assert _buy(client, phone="12345").status_code == 422
    assert _buy(client, company="bot inc").status_code == 422


# --- purchase flow (stub gateway, dev) ---------------------------------------------


def test_full_flow_with_stub(client, db, coupons, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "PAYMENTS_PROVIDER", "stub")
    sent = []
    monkeypatch.setattr("app.livewell.email_notifications.send", lambda to, title, body, **k: sent.append((to, title, body)))
    r = _buy(client, coupon_code="PAYNOW3", amount_paise=1)  # a browser amount is ignored
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["price"]["amount_paise"] == 1_21_250_00 and out["price"]["discount_paise"] == 3_750_00
    pay = out["payment"]
    assert pay["provider"] == "stub" and pay["amount_minor"] == 1_21_250_00
    lead = db.query(ElderProspect).one()
    assert lead.source == "website:buy-now" and lead.stage == "NEW"
    assert _coupon(db, "PAYNOW3").used_count == 0  # counted only once paid

    v = client.post(f"{BASE}/{out['reference']}/verify", json={"order_id": pay["order_id"], "payment_id": "pay_1", "signature": "x"})
    assert v.status_code == 200, v.text
    # The webhook-style second call changes nothing.
    v2 = client.post(f"{BASE}/{out['reference']}/verify", json={"order_id": pay["order_id"], "payment_id": "pay_1", "signature": "x"})
    assert v2.status_code == 200
    db.expire_all()
    plans = db.query(CustomerPlan).all()
    assert len(plans) == 1
    p = plans[0]
    assert (p.status, p.payment_status, p.payment_mode) == ("pending_approval", "paid", "razorpay")
    assert p.amount_paise == 1_21_250_00 and p.discount_paise == 3_750_00 and p.coupon_code == "PAYNOW3"
    assert p.paid_at is not None and p.prospect_id == lead.id and "pay_1" in p.notes
    assert _coupon(db, "PAYNOW3").used_count == 1
    lead = db.get(ElderProspect, lead.id)
    assert lead.stage == "WON" and lead.status == "WON" and lead.converted_elder_id == p.elder_id
    won = db.query(PipelineActivity).filter(PipelineActivity.elder_prospect_id == lead.id,
                                            PipelineActivity.activity_type == "STAGE_CHANGE").all()
    assert len(won) == 1 and "PAYNOW3" in won[0].body
    purchase = db.query(PlanPurchase).one()
    assert purchase.status == "paid" and purchase.gateway_payment_id == "pay_1" and purchase.customer_plan_id == p.id
    titles = [t for _, t, _ in sent]
    assert any(t.startswith("Plan to approve") for t in titles)
    receipt = [s for s in sent if s[1].startswith("Payment received")]
    assert len(receipt) == 1 and receipt[0][0] == ["ravi@example.com"] and "₹1,21,250" in receipt[0][2]
    # Ops sees the coupon on the plan row.
    leads = client.get("/api/v1/sales/leads", headers=admin_headers).json()
    row = next(x for x in leads if x["id"] == lead.id)
    assert row["plan"]["coupon_code"] == "PAYNOW3" and row["plan"]["discount_paise"] == 3_750_00


def test_verify_needs_matching_order(client, coupons):
    out = _buy(client).json()
    r = client.post(f"{BASE}/{out['reference']}/verify", json={"order_id": "order_other", "payment_id": "p", "signature": "s"})
    assert r.status_code == 404
    assert client.post(f"{BASE}/KP-1234567890/verify", json={"order_id": "o", "payment_id": "p", "signature": "s"}).status_code == 404


def test_repeat_buyer_reuses_the_lead(client, db, coupons):
    _buy(client)
    _buy(client, name="Ravi K", phone="+91 98765 12345")
    assert db.query(ElderProspect).count() == 1 and db.query(PlanPurchase).count() == 2


def test_rate_limited_per_ip(db, coupons):
    for _ in range(svc.PURCHASE_LIMIT_PER_HOUR):
        svc.start(db, plan_id="assurance", billing_cycle="yearly", name="A B", phone="9876500001",
                  email="a@b.co", accept_terms=True, source_ip="9.9.9.9")
    with pytest.raises(Exception) as e:
        svc.start(db, plan_id="assurance", billing_cycle="yearly", name="A B", phone="9876500001",
                  email="a@b.co", accept_terms=True, source_ip="9.9.9.9")
    assert getattr(e.value, "status_code", None) == 429


# --- production without a live gateway ----------------------------------------------


def test_prod_stub_never_takes_money(client, db, coupons, monkeypatch):
    monkeypatch.setattr(settings, "PAYMENTS_PROVIDER", "stub")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    notified = []
    monkeypatch.setattr(svc.PublicEnquiryService, "_notify_team", staticmethod(lambda db, row, kind: notified.append(kind)))
    r = _buy(client, coupon_code="PAYNOW5")
    assert r.status_code == 200, r.text
    assert r.json()["payment"] is None and "coming soon" in r.json()["payment_message"]
    assert db.query(ElderProspect).one().source == "website:buy-now"
    assert db.query(PlanPurchase).one().gateway_order_id is None
    assert notified and "PAYNOW5" in notified[0]
    r = client.post(f"{BASE}/{r.json()['reference']}/verify", json={"order_id": "", "payment_id": "p", "signature": "s"})
    assert r.status_code == 404
    assert db.query(CustomerPlan).count() == 0 and _coupon(db, "PAYNOW5").used_count == 0


# --- Razorpay signatures + webhook ---------------------------------------------------


def _razorpay(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENTS_PROVIDER", "razorpay")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_key", raising=False)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "secret_abc", raising=False)
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "whsec_abc", raising=False)


def _stub_order(db, client, monkeypatch, **over):
    monkeypatch.setattr(settings, "PAYMENTS_PROVIDER", "stub")
    out = _buy(client, **over).json()
    return out, db.query(PlanPurchase).order_by(PlanPurchase.id.desc()).first()


def test_checkout_signature_good_and_bad(client, db, coupons, monkeypatch):
    out, p = _stub_order(db, client, monkeypatch)
    _razorpay(monkeypatch)
    bad = client.post(f"{BASE}/{out['reference']}/verify",
                      json={"order_id": p.gateway_order_id, "payment_id": "pay_9", "signature": "forged"})
    assert bad.status_code == 400
    assert db.query(CustomerPlan).count() == 0
    sig = hmac.new(b"secret_abc", f"{p.gateway_order_id}|pay_9".encode(), hashlib.sha256).hexdigest()
    good = client.post(f"{BASE}/{out['reference']}/verify",
                       json={"order_id": p.gateway_order_id, "payment_id": "pay_9", "signature": sig})
    assert good.status_code == 200, good.text
    assert db.query(CustomerPlan).count() == 1


def _hook(client, order_id, amount, event="payment.captured", secret=b"whsec_abc"):
    body = json.dumps({"event": event, "payload": {"payment": {"entity": {
        "id": "pay_w1", "order_id": order_id, "amount": amount}}}}).encode()
    sig = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return client.post(WEBHOOK, content=body, headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"})


def test_webhook_is_idempotent(client, db, coupons, monkeypatch):
    out, p = _stub_order(db, client, monkeypatch, coupon_code="PAYNOW5")
    _razorpay(monkeypatch)
    assert _hook(client, p.gateway_order_id, p.amount_paise + 1).json()["status"] == "ignored"  # amount mismatch
    assert _hook(client, p.gateway_order_id, p.amount_paise, secret=b"wrong").status_code == 400
    assert _hook(client, p.gateway_order_id, p.amount_paise, event="payment.failed").json()["status"] == "ignored"
    for _ in range(3):
        r = _hook(client, p.gateway_order_id, p.amount_paise)
        assert r.status_code == 200 and r.json()["status"] == "plan_paid", r.text
    # The browser callback arriving late changes nothing either.
    sig = hmac.new(b"secret_abc", f"{p.gateway_order_id}|pay_w1".encode(), hashlib.sha256).hexdigest()
    assert client.post(f"{BASE}/{out['reference']}/verify",
                       json={"order_id": p.gateway_order_id, "payment_id": "pay_w1", "signature": sig}).status_code == 200
    db.expire_all()
    assert db.query(CustomerPlan).count() == 1
    assert _coupon(db, "PAYNOW5").used_count == 1
    assert db.query(ElderProspect).one().stage == "WON"
    assert db.query(PlanPurchase).one().gateway_payment_id == "pay_w1"


# --- coupons on plans in Ops ----------------------------------------------------------


def test_won_with_coupon(client, db, coupons, auth_headers):
    lead = client.post("/api/v1/sales/leads", headers=auth_headers,
                       json={"name": "Asha Rao", "source": "Phone call", "phone": "9876543210"}).json()
    bad = client.post(f"/api/v1/sales/leads/{lead['id']}/move", headers=auth_headers,
                      json={"to": "WON", "plan_id": "privilege", "billing_cycle": "yearly", "coupon_code": "OLD"})
    assert bad.status_code == 400 and db.query(CustomerPlan).count() == 0
    r = client.post(f"/api/v1/sales/leads/{lead['id']}/move", headers=auth_headers,
                    json={"to": "WON", "plan_id": "privilege", "billing_cycle": "yearly", "coupon_code": "paynow5"})
    assert r.status_code == 200, r.text
    plan = r.json()["customer_plan"]
    assert plan["amount_paise"] == 1_18_750_00 and plan["discount_paise"] == 6_250_00 and plan["coupon_code"] == "PAYNOW5"
    assert plan["payment_status"] == "unpaid"
    assert _coupon(db, "PAYNOW5").used_count == 1


def test_assign_plan_with_coupon_and_price_check(client, db, coupons, auth_headers, admin_headers):
    r = client.post("/api/v1/sales/plan-price", headers=auth_headers,
                    json={"plan_id": "assurance", "billing_cycle": "monthly", "coupon_code": "PAYNOW3"})
    assert r.status_code == 200 and r.json()["amount_paise"] == 5_820_00
    lead = client.post("/api/v1/sales/leads", headers=auth_headers,
                       json={"name": "Meena Iyer", "phone": "9876543299"}).json()
    won = client.post(f"/api/v1/sales/leads/{lead['id']}/move", headers=auth_headers,
                      json={"to": "WON", "plan_id": "assurance", "billing_cycle": "monthly"}).json()
    elder_id = won["customer_plan"]["elder_id"]
    # One plan already waits for approval: an admin approves it first.
    client.post(f"/api/v1/sales/plans/{won['customer_plan']['id']}/authorize", headers=admin_headers,
                json={"payment_mode": "cash", "paid": True})
    full = client.post(f"/api/v1/sales/customers/{elder_id}/plans", headers=auth_headers,
                       json={"plan_id": "assurance", "billing_cycle": "monthly", "coupon_code": "FULL"})
    assert full.status_code == 400
    r = client.post(f"/api/v1/sales/customers/{elder_id}/plans", headers=auth_headers,
                    json={"plan_id": "assurance", "billing_cycle": "monthly", "coupon_code": "PAYNOW3"})
    assert r.status_code == 201, r.text
    assert r.json()["amount_paise"] == 5_820_00 and r.json()["coupon_code"] == "PAYNOW3"
    assert _coupon(db, "PAYNOW3").used_count == 1
