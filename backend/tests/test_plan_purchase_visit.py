"""Pay-as-you-go "Buy now": one Single priority visit paid on the website (31 Oct 2026)."""

import hashlib
import hmac
import json
from datetime import timedelta

import pytest

from app.core.config import settings
from app.livewell import plan_purchase_service as svc
from app.livewell.family_service_requests import _requests
from app.models.commerce import Coupon
from app.models.customer_plan import CustomerPlan
from app.models.elder import Elder
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
        Coupon(tenant_id=tid, code="PAYNOW5", kind="percent", value=500, used_count=0, active=True),
        Coupon(tenant_id=tid, code="FLAT1000", kind="amount", value=1000_00, used_count=0, active=True),
        Coupon(tenant_id=tid, code="FULL", kind="percent", value=500, used_count=2, max_uses=2, active=True),
    ]
    db.add_all(rows)
    db.commit()
    return {c.code: c for c in rows}


def _tomorrow() -> str:
    return (svc._ist_today() + timedelta(days=1)).isoformat()


def _buy(client, **over):
    body = {
        "plan_id": "single-visit", "billing_cycle": "once", "name": "Sita Rao",
        "phone": "9876512399", "email": "sita@example.com", "accept_terms": True,
        "need": "physiotherapy", "preferred_date": _tomorrow(), "time_of_day": "morning",
    }
    body.update(over)
    return client.post(BASE, json=body)


def _coupon(db, code):
    db.expire_all()
    return db.query(Coupon).filter(Coupon.code == code).one()


def _visit_requests(db):
    db.expire_all()
    return [r for e in db.query(Elder).all() for r in _requests(e)]


# --- price -------------------------------------------------------------------------


def test_visit_price_in_paise(client, coupons):
    r = client.post(f"{BASE}/quote", json={"plan_id": "single-visit", "billing_cycle": "once"})
    assert r.status_code == 200, r.text
    assert r.json() == {
        "plan_id": "single-visit", "plan_name": "Single priority visit", "billing_cycle": "once",
        "list_paise": 3_500_00, "discount_paise": 0, "amount_paise": 3_500_00, "coupon_code": None,
        "visit_paise": 3_400_00, "registration_paise": 100_00,
    }
    r = client.post(f"{BASE}/quote", json={"plan_id": "single-visit", "billing_cycle": "once", "coupon_code": "paynow5"})
    assert (r.json()["discount_paise"], r.json()["amount_paise"]) == (175_00, 3_325_00)
    r = client.post(f"{BASE}/quote", json={"plan_id": "single-visit", "billing_cycle": "once", "coupon_code": "FLAT1000"})
    assert r.json()["amount_paise"] == 2_500_00
    assert client.post(f"{BASE}/quote", json={"plan_id": "single-visit", "billing_cycle": "once",
                                              "coupon_code": "FULL"}).status_code == 400
    assert client.post(f"{BASE}/quote", json={"plan_id": "single-visit", "billing_cycle": "yearly"}).status_code == 422


@pytest.mark.parametrize("over", [
    {"need": ""}, {"need": "haircut"}, {"need": "other", "need_note": ""},
    {"preferred_date": "2020-01-01"}, {"preferred_date": "not-a-date"}, {"time_of_day": "midnight"},
    {"billing_cycle": "monthly"},
])
def test_visit_form_checked_before_saving(client, db, coupons, over):
    assert _buy(client, **over).status_code == 422
    assert db.query(PlanPurchase).count() == 0 and db.query(ElderProspect).count() == 0


def test_today_is_too_soon_and_optional_fields(client, db, coupons, monkeypatch):
    monkeypatch.setattr(settings, "PAYMENTS_PROVIDER", "stub")
    assert _buy(client, preferred_date=svc._ist_today().isoformat()).status_code == 422
    r = _buy(client, need="other", need_note="Help after cataract surgery", preferred_date=None, time_of_day=None)
    assert r.status_code == 200, r.text
    assert db.query(PlanPurchase).one().details == {
        "need": "other", "note": "Help after cataract surgery", "preferred_date": None, "time_of_day": None}


# --- purchase -> verify -> request ---------------------------------------------------


def test_visit_flow_creates_one_paid_request(client, db, coupons, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "PAYMENTS_PROVIDER", "stub")
    sent = []
    monkeypatch.setattr("app.livewell.email_notifications.send", lambda to, title, body, **k: sent.append((to, title, body)))
    r = _buy(client, coupon_code="PAYNOW5", amount_paise=1)  # a browser amount is ignored
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["price"]["amount_paise"] == 3_325_00 and out["payment"]["amount_minor"] == 3_325_00
    lead = db.query(ElderProspect).one()
    assert lead.source == "website:buy-now-visit" and lead.stage == "NEW"
    assert _coupon(db, "PAYNOW5").used_count == 0

    body = {"order_id": out["payment"]["order_id"], "payment_id": "pay_v1", "signature": "x"}
    for _ in range(2):  # a repeat (or the webhook) changes nothing
        v = client.post(f"{BASE}/{out['reference']}/verify", json=body)
        assert v.status_code == 200 and v.json()["paid"] is True, v.text

    db.expire_all()
    assert db.query(CustomerPlan).count() == 0  # a visit is not a plan
    reqs = _visit_requests(db)
    assert len(reqs) == 1
    req = reqs[0]
    assert req["service_type"] == "physiotherapy" and req["status"] == "requested"
    assert req["payment_status"] == "paid" and req["paid_online_minor"] == 3_325_00
    assert req["quoted_amount_minor"] == 0  # never refunded to the wallet on cancel
    assert out["reference"] in req["notes"] and "pay_v1" in req["notes"] and "PAYNOW5" in req["notes"]
    assert req["preferred_at"] is not None and "morning" in req["notes"]
    purchase = db.query(PlanPurchase).one()
    assert purchase.status == "paid" and purchase.service_request_id == req["id"] and purchase.customer_plan_id is None
    assert _coupon(db, "PAYNOW5").used_count == 1
    lead = db.get(ElderProspect, lead.id)
    assert lead.stage == "WON" and lead.status == "WON" and lead.converted_elder_id
    won = db.query(PipelineActivity).filter(PipelineActivity.elder_prospect_id == lead.id,
                                            PipelineActivity.activity_type == "STAGE_CHANGE").all()
    assert len(won) == 1 and "Physiotherapy" in won[0].body and won[0].metadata_["service_request_id"] == req["id"]

    receipt = [s for s in sent if s[1].startswith("Payment received")]
    assert len(receipt) == 1 and receipt[0][0] == ["sita@example.com"] and "₹3,325" in receipt[0][2]
    assert "₹3,400 visit + ₹100 registration" in receipt[0][2]

    # Ops: Visits -> Requests shows it, with the amount paid online.
    attn = client.get("/api/v1/home-safety/dashboard/attention", headers=admin_headers)
    assert attn.status_code == 200, attn.text
    row = next(x for x in attn.json()["requests"] if x["id"] == req["id"])
    assert row["paid_online_minor"] == 3_325_00 and row["label"] == "Physiotherapy session"


def test_staff_decline_does_not_refund_to_wallet(client, db, coupons, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "PAYMENTS_PROVIDER", "stub")
    out = _buy(client).json()
    client.post(f"{BASE}/{out['reference']}/verify",
                json={"order_id": out["payment"]["order_id"], "payment_id": "pay_v2", "signature": "x"})
    req = _visit_requests(db)[0]
    elder = db.get(Elder, db.query(ElderProspect).one().converted_elder_id)
    r = client.patch(f"/api/v1/home-safety/care/elders/{elder.id}/service-requests/{req['id']}",
                     json={"status": "declined"}, headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["payment_status"] == "paid"
    from app.models.family_wallet import WalletTransaction

    assert db.query(WalletTransaction).count() == 0


def test_webhook_and_verify_idempotent(client, db, coupons, monkeypatch):
    monkeypatch.setattr(settings, "PAYMENTS_PROVIDER", "stub")
    out = _buy(client, coupon_code="PAYNOW5").json()
    p = db.query(PlanPurchase).one()
    monkeypatch.setattr(settings, "PAYMENTS_PROVIDER", "razorpay")
    monkeypatch.setattr(settings, "RAZORPAY_KEY_ID", "rzp_test_key", raising=False)
    monkeypatch.setattr(settings, "RAZORPAY_KEY_SECRET", "secret_abc", raising=False)
    monkeypatch.setattr(settings, "RAZORPAY_WEBHOOK_SECRET", "whsec_abc", raising=False)
    body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {
        "id": "pay_w9", "order_id": p.gateway_order_id, "amount": p.amount_paise}}}}).encode()
    sig = hmac.new(b"whsec_abc", body, hashlib.sha256).hexdigest()
    for _ in range(3):
        r = client.post(WEBHOOK, content=body, headers={"X-Razorpay-Signature": sig, "Content-Type": "application/json"})
        assert r.status_code == 200 and r.json()["status"] == "plan_paid", r.text
    vsig = hmac.new(b"secret_abc", f"{p.gateway_order_id}|pay_w9".encode(), hashlib.sha256).hexdigest()
    assert client.post(f"{BASE}/{out['reference']}/verify",
                       json={"order_id": p.gateway_order_id, "payment_id": "pay_w9", "signature": vsig}).status_code == 200
    assert len(_visit_requests(db)) == 1
    assert db.query(CustomerPlan).count() == 0
    assert _coupon(db, "PAYNOW5").used_count == 1
    assert db.query(ElderProspect).one().stage == "WON"


def test_prod_stub_visit_never_takes_money(client, db, coupons, monkeypatch):
    monkeypatch.setattr(settings, "PAYMENTS_PROVIDER", "stub")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    notified = []
    monkeypatch.setattr(svc.PublicEnquiryService, "_notify_team", staticmethod(lambda db, row, kind: notified.append(kind)))
    r = _buy(client)
    assert r.status_code == 200, r.text
    assert r.json()["payment"] is None and "coming soon" in r.json()["payment_message"]
    assert db.query(ElderProspect).one().source == "website:buy-now-visit"
    assert notified and "Physiotherapy" in notified[0]
    r = client.post(f"{BASE}/{r.json()['reference']}/verify", json={"order_id": "", "payment_id": "p", "signature": "s"})
    assert r.status_code == 404
    assert _visit_requests(db) == [] and db.query(CustomerPlan).count() == 0
