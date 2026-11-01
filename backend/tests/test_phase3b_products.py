"""Phase 3B: new/edit product, coupon edit + clear errors, install booking with caregiver,
reject / cancel / reschedule orders, paid-order cancel refunds to the wallet."""

from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.livewell.family_elder_access import ensure_family_elder_link
from app.livewell.wallet_service import WalletService
from app.models.care_job import CareJob
from app.models.user import User

F = "/api/v1/home-safety/family"


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _when(days=2, hour=10):
    d = datetime.now(timezone.utc).replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(days=days)
    return d.isoformat()


def _order(client, seed_tenant, headers=None, discount_bp=0):
    admin = _login(client, "admin@test.example")
    p = next(x for x in client.get("/api/v1/products", headers=admin).json() if x["name"] == "Fixed grab bar")
    client.put(f"/api/v1/products/{p['id']}", json={"cost_paise": 100000, "margin_bp": 3000}, headers=admin)
    res = client.post(
        "/api/v1/orders",
        json={"elder_id": seed_tenant["elder"].id, "lines": [{"product_id": p["id"], "qty": 1}], "discount_bp": discount_bp},
        headers=headers or admin,
    )
    assert res.status_code == 201, res.text
    return admin, res.json()


# --- Products ------------------------------------------------------------------------


def test_admin_creates_and_edits_product(client, seed_tenant):
    admin = _login(client, "admin@test.example")
    assert len(client.get("/api/v1/products", headers=admin).json()) == 117  # seeds the defaults (9 originals + catalog)
    res = client.post(
        "/api/v1/products",
        json={"name": "Night light", "category": "Bedroom", "description": "Motion sensor", "cost_paise": 50000, "margin_bp": 2000},
        headers=admin,
    )
    assert res.status_code == 201, res.text
    p = res.json()
    assert p["price_paise"] == 60000 and p["category"] == "Bedroom"
    edit = client.put(f"/api/v1/products/{p['id']}", json={"name": "Night light (motion)", "description": "Plug-in"}, headers=admin)
    assert edit.status_code == 200 and edit.json()["name"] == "Night light (motion)"
    # Clear 400s, never a 500
    assert client.post("/api/v1/products", json={"name": "  "}, headers=admin).status_code == 400
    dup = client.post("/api/v1/products", json={"name": "Shower chair"}, headers=admin)
    assert dup.status_code == 400 and "already exists" in dup.text
    assert client.put(f"/api/v1/products/{p['id']}", json={"name": ""}, headers=admin).status_code == 400


def test_manager_cannot_create_product(client, seed_tenant, auth_headers):
    assert client.post("/api/v1/products", json={"name": "X"}, headers=auth_headers).status_code == 403


def test_family_never_sees_cost_or_margin(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    user = User(
        email="fam.3b@test.example", password_hash=hash_password("testpass123"), first_name="P", last_name="R",
        role="ELDER_PORTAL", tenant_id=elder.tenant_id, elder_id=elder.id,
    )
    db.add(user)
    db.flush()
    ensure_family_elder_link(db, user, elder)
    db.commit()
    admin, order = _order(client, seed_tenant)
    client.post(f"/api/v1/orders/{order['id']}/status", json={"status": "quoted"}, headers=admin)
    fam = _login(client, "fam.3b@test.example")
    # Staff-only endpoints are closed to the family
    assert client.get("/api/v1/products", headers=fam).status_code == 403
    assert client.get("/api/v1/orders", headers=fam).status_code == 403
    for path in ("/products", "/quotes"):
        body = client.get(f"{F}{path}", headers=fam).text
        assert "cost_paise" not in body and "margin" not in body, path


# --- Coupons -------------------------------------------------------------------------


def test_coupon_edit_and_clear_errors(client, seed_tenant):
    admin = _login(client, "admin@test.example")
    c = client.post("/api/v1/coupons", json={"code": "NEW15", "kind": "percent", "value": 1500}, headers=admin).json()
    ok = client.put(f"/api/v1/coupons/{c['id']}", json={"value": 2000, "note": "  Spring  ", "max_uses": 5}, headers=admin)
    assert ok.status_code == 200, ok.text
    assert ok.json()["value"] == 2000 and ok.json()["note"] == "Spring" and ok.json()["max_uses"] == 5
    # back to no limit
    assert client.put(f"/api/v1/coupons/{c['id']}", json={"max_uses": None}, headers=admin).json()["max_uses"] is None
    bad = [
        ({"value": 0}, "above zero"),
        ({"value": 20000}, "100%"),
        ({"max_uses": 0}, "1 or more"),
    ]
    for body, words in bad:
        r = client.put(f"/api/v1/coupons/{c['id']}", json=body, headers=admin)
        assert r.status_code == 400 and words in r.json()["detail"], (body, r.text)
    dup = client.post("/api/v1/coupons", json={"code": "new15", "kind": "percent", "value": 100}, headers=admin)
    assert dup.status_code == 400 and "already exists" in dup.text
    assert client.post("/api/v1/coupons", json={"code": "BIG", "value": 20000}, headers=admin).status_code == 400


# --- Orders: install booking, reschedule, reject, cancel -----------------------------


def test_schedule_install_with_caregiver_and_reschedule(client, db, seed_tenant, auth_headers):
    admin, order = _order(client, seed_tenant)
    cg = seed_tenant["caregiver"]
    res = client.post(f"/api/v1/orders/{order['id']}/install", json={"scheduled_at": _when(), "caregiver_id": cg.id}, headers=auth_headers)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["order"]["status"] == "scheduled"
    job = db.get(CareJob, out["job"]["id"])
    assert job.kind == "install" and job.caregiver_id == cg.id and job.request_id == f"order-{order['id']}"
    assert out["order"]["job_id"] == job.id

    # Reschedule moves the same job
    later = client.post(f"/api/v1/orders/{order['id']}/install", json={"scheduled_at": _when(days=4)}, headers=auth_headers)
    assert later.status_code == 200, later.text
    assert later.json()["job"]["id"] == job.id
    assert db.query(CareJob).filter(CareJob.request_id == f"order-{order['id']}").count() == 1

    # Cancelling a scheduled order cancels its installation visit
    cancel = client.post(f"/api/v1/orders/{order['id']}/status", json={"status": "cancelled", "reason": "Family changed mind"}, headers=auth_headers)
    assert cancel.status_code == 200, cancel.text
    db.refresh(job)
    assert job.status == "cancelled"
    assert "Cancelled: Family changed mind" in cancel.json()["note"]


def test_install_clash_needs_force(client, db, seed_tenant, auth_headers):
    _, o1 = _order(client, seed_tenant)
    _, o2 = _order(client, seed_tenant)
    cg = seed_tenant["caregiver"].id
    at = _when(days=3)
    assert client.post(f"/api/v1/orders/{o1['id']}/install", json={"scheduled_at": at, "caregiver_id": cg}, headers=auth_headers).status_code == 200
    clash = client.post(f"/api/v1/orders/{o2['id']}/install", json={"scheduled_at": at, "caregiver_id": cg}, headers=auth_headers)
    assert clash.status_code == 409 and clash.json()["detail"].endswith("Book anyway?")
    # Nothing half-done: order still approved, no job
    assert client.get(f"/api/v1/orders?elder_id={seed_tenant['elder'].id}", headers=auth_headers).json()[0]["status"] == "approved"
    forced = client.post(f"/api/v1/orders/{o2['id']}/install", json={"scheduled_at": at, "caregiver_id": cg, "force": True}, headers=auth_headers)
    assert forced.status_code == 200, forced.text


def test_cannot_schedule_pending_or_cancelled(client, seed_tenant, auth_headers):
    admin, pending = _order(client, seed_tenant, headers=auth_headers, discount_bp=2000)
    assert pending["status"] == "pending_approval"
    r = client.post(f"/api/v1/orders/{pending['id']}/install", json={"scheduled_at": _when()}, headers=auth_headers)
    assert r.status_code == 400 and "approve" in r.text
    # Admin rejects with a reason
    rej = client.post(f"/api/v1/orders/{pending['id']}/status", json={"status": "cancelled", "reason": "Too much discount"}, headers=admin)
    assert rej.status_code == 200 and rej.json()["status"] == "cancelled"
    assert "Rejected: Too much discount" in rej.json()["note"]
    assert client.post(f"/api/v1/orders/{pending['id']}/install", json={"scheduled_at": _when()}, headers=admin).status_code == 400


def test_cancel_paid_scheduled_order_refunds_wallet(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    user = User(
        email="fam.3b.pay@test.example", password_hash=hash_password("testpass123"), first_name="P", last_name="R",
        role="ELDER_PORTAL", tenant_id=elder.tenant_id, elder_id=elder.id,
    )
    db.add(user)
    db.flush()
    ensure_family_elder_link(db, user, elder)
    db.commit()
    admin, order = _order(client, seed_tenant)
    client.post(f"/api/v1/orders/{order['id']}/status", json={"status": "quoted"}, headers=admin)
    wallet = WalletService.get_or_create(db, elder)
    WalletService.record(db, wallet, kind="recharge", amount_minor=order["total_paise"], idempotency_key="recharge:3b")
    fam = _login(client, "fam.3b.pay@test.example")
    assert client.post(f"{F}/quotes/{order['id']}/accept", headers=fam).json()["paid"] is True
    assert WalletService.get_or_create(db, elder).balance_minor == 0
    booked = client.post(f"/api/v1/orders/{order['id']}/install", json={"scheduled_at": _when()}, headers=admin)
    assert booked.status_code == 200 and booked.json()["order"]["status"] == "scheduled"
    cancel = client.post(f"/api/v1/orders/{order['id']}/status", json={"status": "cancelled"}, headers=admin)
    assert cancel.status_code == 200, cancel.text
    assert WalletService.get_or_create(db, elder).balance_minor == order["total_paise"]
    assert isinstance(WalletService.get_or_create(db, elder).balance_minor, int)


# --- Phase 3 fixes ---------------------------------------------------------------------


def _coupon_order(client, seed_tenant, admin, code):
    p = next(x for x in client.get("/api/v1/products", headers=admin).json() if x["name"] == "Fixed grab bar")
    client.put(f"/api/v1/products/{p['id']}", json={"cost_paise": 100000, "margin_bp": 3000}, headers=admin)
    return client.post(
        "/api/v1/orders",
        json={"elder_id": seed_tenant["elder"].id, "lines": [{"product_id": p["id"], "qty": 1}], "coupon_code": code},
        headers=admin,
    )


def test_coupon_last_use_is_atomic_and_given_back_on_cancel(client, db, seed_tenant, monkeypatch):
    from app.livewell import commerce
    from app.models.commerce import Coupon

    admin = _login(client, "admin@test.example")
    c = client.post("/api/v1/coupons", json={"code": "ONCE", "kind": "percent", "value": 500}, headers=admin).json()
    client.put(f"/api/v1/coupons/{c['id']}", json={"max_uses": 1}, headers=admin)

    first = _coupon_order(client, seed_tenant, admin, "ONCE")
    assert first.status_code == 201, first.text
    assert db.get(Coupon, c["id"]).used_count == 1
    assert _coupon_order(client, seed_tenant, admin, "ONCE").status_code == 400

    # Cancelling the unpaid order frees the use — once.
    cancel = client.post(f"/api/v1/orders/{first.json()['id']}/status", json={"status": "cancelled"}, headers=admin)
    assert cancel.status_code == 200, cancel.text
    db.expire_all()
    assert db.get(Coupon, c["id"]).used_count == 0
    assert client.post(f"/api/v1/orders/{first.json()['id']}/status", json={"status": "cancelled"}, headers=admin).status_code == 400
    db.expire_all()
    assert db.get(Coupon, c["id"]).used_count == 0

    # Race: someone takes the last use between the check and the increment.
    real = commerce.price_order

    def racing(db_, *a, **kw):
        out = real(db_, *a, **kw)
        db_.query(Coupon).filter(Coupon.id == c["id"]).update({"used_count": 1})
        return out

    monkeypatch.setattr(commerce, "price_order", racing)
    raced = _coupon_order(client, seed_tenant, admin, "ONCE")
    assert raced.status_code == 400 and "used up" in raced.text


def test_family_decline_gives_coupon_back(client, db, seed_tenant):
    from app.models.commerce import Coupon

    elder = seed_tenant["elder"]
    user = User(email="fam.3b.dec@test.example", password_hash=hash_password("testpass123"), first_name="D",
                last_name="C", role="ELDER_PORTAL", tenant_id=elder.tenant_id, elder_id=elder.id)
    db.add(user)
    db.flush()
    ensure_family_elder_link(db, user, elder)
    db.commit()
    admin = _login(client, "admin@test.example")
    c = client.post("/api/v1/coupons", json={"code": "DEC5", "kind": "percent", "value": 500}, headers=admin).json()
    order = _coupon_order(client, seed_tenant, admin, "DEC5").json()
    client.post(f"/api/v1/orders/{order['id']}/status", json={"status": "quoted"}, headers=admin)
    fam = _login(client, "fam.3b.dec@test.example")
    assert client.post(f"{F}/quotes/{order['id']}/decline", json={}, headers=fam).status_code == 200
    db.expire_all()
    assert db.get(Coupon, c["id"]).used_count == 0


def test_cancel_with_installer_on_the_way_needs_force(client, db, seed_tenant, auth_headers):
    _, order = _order(client, seed_tenant)
    booked = client.post(f"/api/v1/orders/{order['id']}/install", json={"scheduled_at": _when()}, headers=auth_headers).json()
    job = db.get(CareJob, booked["job"]["id"])
    job.status = "on_the_way"
    db.commit()
    url = f"/api/v1/orders/{order['id']}/status"
    blocked = client.post(url, json={"status": "cancelled"}, headers=auth_headers)
    assert blocked.status_code == 409 and "on the way" in blocked.json()["detail"]
    db.refresh(job)
    assert job.status == "on_the_way"
    forced = client.post(url, json={"status": "cancelled", "force": True}, headers=auth_headers)
    assert forced.status_code == 200, forced.text


def test_paid_order_unscheduled_goes_back_to_family_accepted(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    user = User(email="fam.3b.back@test.example", password_hash=hash_password("testpass123"), first_name="B",
                last_name="K", role="ELDER_PORTAL", tenant_id=elder.tenant_id, elder_id=elder.id)
    db.add(user)
    db.flush()
    ensure_family_elder_link(db, user, elder)
    db.commit()
    admin, order = _order(client, seed_tenant)
    client.post(f"/api/v1/orders/{order['id']}/status", json={"status": "quoted"}, headers=admin)
    wallet = WalletService.get_or_create(db, elder)
    WalletService.record(db, wallet, kind="recharge", amount_minor=order["total_paise"], idempotency_key="recharge:3b-back")
    fam = _login(client, "fam.3b.back@test.example")
    assert client.post(f"{F}/quotes/{order['id']}/accept", headers=fam).json()["paid"] is True
    client.post(f"/api/v1/orders/{order['id']}/install", json={"scheduled_at": _when()}, headers=admin)
    back = client.post(f"/api/v1/orders/{order['id']}/status", json={"status": "approved"}, headers=admin)
    assert back.status_code == 200 and back.json()["status"] == "family_accepted"
    quotes = client.get(f"{F}/quotes", headers=fam).json()
    mine = next(q for q in quotes if q["id"] == order["id"])
    assert mine["status_label"] == "Paid — we'll book a time"


def test_concurrent_booking_keeps_first_job(client, db, seed_tenant, auth_headers, monkeypatch):
    from app.livewell import commerce

    _, order = _order(client, seed_tenant)
    first = client.post(f"/api/v1/orders/{order['id']}/install", json={"scheduled_at": _when()}, headers=auth_headers).json()
    # Simulate a second booking that read the order before the first one landed.
    monkeypatch.setattr(commerce, "_open_install_jobs", lambda db_, o: [])
    res = client.post(f"/api/v1/orders/{order['id']}/install", json={"scheduled_at": _when(days=5), "force": True}, headers=auth_headers)
    assert res.status_code == 409, res.text
    jobs = db.query(CareJob).filter(CareJob.request_id == f"order-{order['id']}").all()
    open_jobs = [j for j in jobs if j.status != "cancelled"]
    assert [j.id for j in open_jobs] == [first["job"]["id"]]
