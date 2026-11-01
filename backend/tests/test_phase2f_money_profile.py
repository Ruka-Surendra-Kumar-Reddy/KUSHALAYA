"""Phase 2F: quote → family Approve & pay from the wallet, Not now, My details, details-change requests."""

from app.core.security import hash_password
from app.livewell.family_elder_access import ensure_family_elder_link
from app.livewell.wallet_service import WalletService
from app.models.commerce import Order
from app.models.elder import Elder
from app.models.user import User

F = "/api/v1/home-safety/family"


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _family_user(db, elder, tag="a"):
    user = User(
        email=f"fam.{tag}.2f@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Priya",
        last_name="Rao",
        role="ELDER_PORTAL",
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
    )
    db.add(user)
    db.flush()
    ensure_family_elder_link(db, user, elder)
    db.commit()
    return user


def _quoted_order(client, seed_tenant):
    admin = _login(client, "admin@test.example")
    products = client.get("/api/v1/products", headers=admin).json()
    p = next(x for x in products if x["name"] == "Fixed grab bar")
    client.put(f"/api/v1/products/{p['id']}", json={"cost_paise": 100000, "margin_bp": 3000}, headers=admin)
    order = client.post(
        "/api/v1/orders",
        json={"elder_id": seed_tenant["elder"].id, "lines": [{"product_id": p["id"], "qty": 2}]},
        headers=admin,
    ).json()
    assert order["status"] == "approved"
    sent = client.post(f"/api/v1/orders/{order['id']}/status", json={"status": "quoted"}, headers=admin)
    assert sent.status_code == 200, sent.text
    assert sent.json()["status"] == "quoted"
    assert sent.json()["quoted_at"]
    return admin, sent.json()


def _top_up(db, elder, amount):
    wallet = WalletService.get_or_create(db, elder)
    WalletService.record(db, wallet, kind="recharge", amount_minor=amount, idempotency_key=f"recharge:t{amount}")
    return wallet


def test_family_sees_quote_without_cost_or_margin(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _login(client, _family_user(db, elder).email)
    _admin, order = _quoted_order(client, seed_tenant)

    quotes = client.get(f"{F}/quotes", headers=fam).json()
    assert len(quotes) == 1
    q = quotes[0]
    assert q["needs_action"] is True
    assert q["total_paise"] == 260000 + 260000 * 18 // 100
    assert q["lines"][0]["qty"] == 2 and q["lines"][0]["name"] == "Fixed grab bar"
    text = str(q)
    assert "cost" not in text and "margin" not in text
    assert order["id"] == q["id"]


def test_accept_pays_from_wallet_computed_server_side(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _login(client, _family_user(db, elder).email)
    _admin, order = _quoted_order(client, seed_tenant)
    total = order["total_paise"]

    # Not enough money: nothing is debited, the family is told how much to top up.
    _top_up(db, elder, 100000)
    res = client.post(f"{F}/quotes/{order['id']}/accept", json={"total_paise": 1}, headers=fam).json()
    assert res["paid"] is False
    assert res["shortfall_paise"] == total - 100000
    assert db.get(Order, order["id"]).status == "quoted"

    _top_up(db, elder, total)
    res = client.post(f"{F}/quotes/{order['id']}/accept", json={"total_paise": 1}, headers=fam).json()
    assert res["paid"] is True
    assert res["quote"]["status"] == "family_accepted"
    db.expire_all()
    o = db.get(Order, order["id"])
    assert o.paid_paise == total and o.paid_at is not None and o.wallet_transaction_id
    wallet = WalletService.get_or_create(db, elder)
    assert wallet.balance_minor == 100000  # (100000 + total) - total

    # Tapping again never debits twice.
    again = client.post(f"{F}/quotes/{order['id']}/accept", headers=fam).json()
    assert again["paid"] is True
    db.expire_all()
    assert WalletService.get_or_create(db, elder).balance_minor == 100000


def test_staff_cannot_mark_family_accepted_and_cancel_refunds(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _login(client, _family_user(db, elder).email)
    admin, order = _quoted_order(client, seed_tenant)
    bad = client.post(f"/api/v1/orders/{order['id']}/status", json={"status": "family_accepted"}, headers=admin)
    assert bad.status_code == 400

    _top_up(db, elder, order["total_paise"])
    client.post(f"{F}/quotes/{order['id']}/accept", headers=fam)
    sched = client.post(f"/api/v1/orders/{order['id']}/status", json={"status": "scheduled"}, headers=admin)
    assert sched.status_code == 200, sched.text
    cancel = client.post(f"/api/v1/orders/{order['id']}/status", json={"status": "cancelled"}, headers=admin)
    assert cancel.status_code == 200, cancel.text
    db.expire_all()
    assert WalletService.get_or_create(db, elder).balance_minor == order["total_paise"]


def test_decline_cancels_with_note(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _login(client, _family_user(db, elder).email)
    _admin, order = _quoted_order(client, seed_tenant)
    res = client.post(f"{F}/quotes/{order['id']}/decline", json={"note": "After Diwali"}, headers=fam)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "cancelled"
    db.expire_all()
    o = db.get(Order, order["id"])
    assert o.status == "cancelled" and o.family_note == "After Diwali"
    assert client.post(f"{F}/quotes/{order['id']}/accept", headers=fam).status_code == 400


def test_other_family_cannot_see_or_pay_quote(client, db, seed_tenant):
    other_elder = Elder(tenant_id=seed_tenant["tenant"].id, first_name="Other", last_name="Senior")
    db.add(other_elder)
    db.flush()
    other = _login(client, _family_user(db, other_elder, tag="b").email)
    _admin, order = _quoted_order(client, seed_tenant)
    assert client.get(f"{F}/quotes", headers=other).json() == []
    assert client.post(f"{F}/quotes/{order['id']}/accept", headers=other).status_code == 404
    assert client.post(f"{F}/quotes/{order['id']}/decline", json={}, headers=other).status_code == 404


def test_my_details_update_scoped_to_own_user_and_elder(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    user = _family_user(db, elder)
    fam = _login(client, user.email)
    res = client.put(
        f"{F}/my-details",
        json={"first_name": "Priyanka", "phone": "+91 98765 43210",
              "emergency_contact_name": "Ravi", "emergency_contact_phone": "+91 90000 00000"},
        headers=fam,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["first_name"] == "Priyanka" and body["phone"] == "+91 98765 43210"
    db.expire_all()
    assert db.get(User, user.id).first_name == "Priyanka"
    e = db.get(Elder, elder.id)
    assert e.emergency_contact_name == "Ravi"
    # Other staff accounts untouched.
    assert db.get(User, seed_tenant["admin"].id).first_name == "Test"

    assert client.put(f"{F}/my-details", json={"phone": "call me"}, headers=fam).status_code == 400
    assert client.put(f"{F}/my-details", json={"first_name": " "}, headers=fam).status_code == 400
    # Health fields are not editable here.
    client.put(f"{F}/my-details", json={"medical_conditions": "none"}, headers=fam)
    db.expire_all()
    assert db.get(Elder, elder.id).medical_conditions is None
    assert client.get(f"{F}/my-details", headers=fam).json()["emergency_contact_phone"] == "+91 90000 00000"


def test_details_change_request_created(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _login(client, _family_user(db, elder).email)
    assert client.post(f"{F}/details-change-request", json={}, headers=fam).status_code == 400
    res = client.post(f"{F}/details-change-request", json={"allergies": "Penicillin"}, headers=fam)
    assert res.status_code == 200, res.text
    assert res.json()["service_type"] == "details_change"
    assert "Penicillin" in res.json()["notes"]
    rows = client.get(f"{F}/service-requests", headers=fam).json()
    assert rows[0]["service_type"] == "details_change"
    admin = _login(client, "admin@test.example")
    staff = client.get(f"/api/v1/home-safety/care/elders/{elder.id}/service-requests", headers=admin)
    assert staff.status_code == 200, staff.text
    assert any(r["service_type"] == "details_change" for r in staff.json())


def test_family_products_have_price_but_no_cost(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _login(client, _family_user(db, elder).email)
    _quoted_order(client, seed_tenant)  # prices the grab bar
    rows = client.get(f"{F}/products", headers=fam).json()
    bar = next(r for r in rows if r["name"] == "Fixed grab bar")
    assert bar["price_paise"] == 130000
    assert all("cost" not in k and "margin" not in k for r in rows for k in r)


def test_accept_after_cancel_refused_and_requote_blocked_when_paid(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _login(client, _family_user(db, elder).email)
    admin, order = _quoted_order(client, seed_tenant)
    # Staff cancel first: the family can no longer pay it, nothing is debited.
    _top_up(db, elder, order["total_paise"])
    assert client.post(f"/api/v1/orders/{order['id']}/status", json={"status": "cancelled"}, headers=admin).status_code == 200
    assert client.post(f"{F}/quotes/{order['id']}/accept", headers=fam).status_code == 400
    db.expire_all()
    assert WalletService.get_or_create(db, elder).balance_minor == order["total_paise"]

    # A paid order can't be sent again as a new quote.
    _admin, o2 = _quoted_order(client, seed_tenant)
    _top_up(db, elder, o2["total_paise"] + 7)
    assert client.post(f"{F}/quotes/{o2['id']}/accept", headers=fam).json()["paid"] is True
    client.post(f"/api/v1/orders/{o2['id']}/status", json={"status": "scheduled"}, headers=admin)
    client.post(f"/api/v1/orders/{o2['id']}/status", json={"status": "approved"}, headers=admin)
    res = client.post(f"/api/v1/orders/{o2['id']}/status", json={"status": "quoted"}, headers=admin)
    assert res.status_code == 400 and "already paid" in res.text


def test_refund_reaches_frozen_wallet(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _login(client, _family_user(db, elder).email)
    admin, order = _quoted_order(client, seed_tenant)
    wallet = _top_up(db, elder, order["total_paise"])
    client.post(f"{F}/quotes/{order['id']}/accept", headers=fam)
    db.expire_all()
    wallet = WalletService.get_or_create(db, elder)
    wallet.status = "frozen"
    db.commit()
    res = client.post(f"/api/v1/orders/{order['id']}/status", json={"status": "cancelled"}, headers=admin)
    assert res.status_code == 200, res.text
    db.expire_all()
    assert WalletService.get_or_create(db, elder).balance_minor == order["total_paise"]


def test_topup_for_quote_pays_it_on_the_server(client, db, seed_tenant, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "PAYMENTS_PROVIDER", "stub")
    elder = seed_tenant["elder"]
    fam = _login(client, _family_user(db, elder).email)
    _admin, order = _quoted_order(client, seed_tenant)
    start = client.post(f"{F}/wallet/recharge", json={"amount_minor": order["total_paise"], "quote_order_id": order["id"]}, headers=fam)
    assert start.status_code == 200, start.text
    assert start.json()["provider"] == "stub"
    settled = client.post(f"{F}/wallet/recharge/settle", json={"transaction_id": start.json()["transaction_id"]}, headers=fam)
    assert settled.status_code == 200, settled.text
    db.expire_all()
    o = db.get(Order, order["id"])
    assert o.status == "family_accepted" and o.paid_paise == order["total_paise"]
    # The app's fallback call is a no-op: still one debit.
    assert client.post(f"{F}/quotes/{order['id']}/accept", headers=fam).json()["paid"] is True
    db.expire_all()
    assert WalletService.get_or_create(db, elder).balance_minor == 0


def test_only_one_open_details_change(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _login(client, _family_user(db, elder).email)
    assert client.post(f"{F}/details-change-request", json={"allergies": "Dust"}, headers=fam).status_code == 200
    again = client.post(f"{F}/details-change-request", json={"allergies": "Pollen"}, headers=fam)
    assert again.status_code == 409
