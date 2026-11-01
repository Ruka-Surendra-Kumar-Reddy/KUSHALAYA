"""Family receipts: derived from the wallet ledger, joined to service requests."""

from datetime import datetime, timezone

from app.core.security import hash_password
from app.livewell.family_elder_access import ensure_family_elder_link
from app.livewell.wallet_service import WalletService
from app.models.elder import Elder
from app.models.user import User


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _family(db, tenant_id, tag):
    elder = Elder(tenant_id=tenant_id, first_name=f"Elder{tag}", last_name="Receipt", status="ACTIVE")
    db.add(elder)
    db.flush()
    user = User(
        email=f"family.{tag}.receipt@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Receipt",
        last_name="Family",
        role="ELDER_PORTAL",
        tenant_id=tenant_id,
        elder_id=elder.id,
    )
    db.add(user)
    db.flush()
    ensure_family_elder_link(db, user, elder)
    db.commit()
    return user, elder


def test_receipts_list_and_detail(db, client, seed_tenant):
    fam, elder = _family(db, seed_tenant["tenant"].id, "a")
    headers = _login(client, fam.email)
    wallet = WalletService.get_or_create(db, elder)
    topup = WalletService.record(
        db,
        wallet,
        kind="recharge",
        amount_minor=150_000,
        idempotency_key="recharge:order_receipt_1",
        gateway="razorpay",
        gateway_order_id="order_r1",
        gateway_payment_id="pay_r1",
        note="Wallet top-up",
        user=fam,
    )
    # A pending (unconfirmed) top-up is not a receipt.
    WalletService.record(
        db,
        wallet,
        kind="recharge",
        amount_minor=5_000,
        idempotency_key="recharge:order_receipt_pending",
        status="pending",
        gateway="razorpay",
        gateway_order_id="order_pending",
    )

    # Staff quotes a service; family approves -> debit receipt joined to the request.
    created = client.post(
        "/api/v1/home-safety/family/service-requests",
        headers=headers,
        json={"service_type": "nurse_pt", "notes": "Physio"},
    )
    assert created.status_code == 200, created.text
    req_id = created.json()["id"]
    elder.manager_user_id = seed_tenant["manager"].id  # staff updates are team-scoped
    db.commit()
    staff = _login(client, seed_tenant["manager"].email)
    quoted = client.patch(
        f"/api/v1/home-safety/care/elders/{elder.id}/service-requests/{req_id}",
        headers=staff,
        json={"status": "confirmed", "quoted_amount_minor": 45_000},
    )
    assert quoted.status_code == 200, quoted.text
    paid = client.post(f"/api/v1/home-safety/family/service-requests/{req_id}/pay", headers=headers)
    assert paid.status_code == 200, paid.text

    res = client.get("/api/v1/home-safety/family/receipts", headers=headers)
    assert res.status_code == 200, res.text
    rows = res.json()
    assert [r["kind"] for r in rows] == ["debit", "recharge"]
    year = datetime.now(timezone.utc).year
    assert all(r["receipt_number"].startswith(f"KA-{year}-") for r in rows)
    assert all(r["status"] == "success" for r in rows)

    debit = rows[0]
    assert debit["amount_minor"] == -45_000
    assert debit["amount_display"] == "-₹450.00"
    assert debit["service_request_id"] == req_id
    assert debit["description"] == "Nurse / physiotherapy"
    assert debit["service_status"] == "confirmed"
    assert debit["payment_method"] == "wallet"
    assert debit["elder_name"] == f"{elder.first_name} {elder.last_name}"
    assert debit["paid_by"] == "Receipt Family"

    top = rows[1]
    assert top["id"] == topup.public_id
    assert top["receipt_number"] == f"KA-{year}-{topup.id}"
    assert top["amount_minor"] == 150_000
    assert top["payment_reference"] == "pay_r1"
    assert top["payment_method"] == "razorpay"

    detail = client.get(f"/api/v1/home-safety/family/receipts/{topup.public_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["receipt_number"] == top["receipt_number"]
    assert detail.json()["tenant_name"] == seed_tenant["tenant"].name

    assert client.get("/api/v1/home-safety/family/receipts/wtx_nope", headers=headers).status_code == 404


def test_refund_shows_as_receipt(db, client, seed_tenant):
    fam, elder = _family(db, seed_tenant["tenant"].id, "b")
    headers = _login(client, fam.email)
    wallet = WalletService.get_or_create(db, elder)
    WalletService.record(
        db, wallet, kind="recharge", amount_minor=100_000, idempotency_key="recharge:rb", user=fam
    )
    req_id = client.post(
        "/api/v1/home-safety/family/service-requests",
        headers=headers,
        json={"service_type": "home_repair"},
    ).json()["id"]
    elder.manager_user_id = seed_tenant["manager"].id  # staff updates are team-scoped
    db.commit()
    staff = _login(client, seed_tenant["manager"].email)
    client.patch(
        f"/api/v1/home-safety/care/elders/{elder.id}/service-requests/{req_id}",
        headers=staff,
        json={"status": "requested", "quoted_amount_minor": 20_000},
    )
    assert client.post(f"/api/v1/home-safety/family/service-requests/{req_id}/pay", headers=headers).status_code == 200
    assert client.post(f"/api/v1/home-safety/family/service-requests/{req_id}/cancel", headers=headers).status_code == 200

    rows = client.get("/api/v1/home-safety/family/receipts", headers=headers).json()
    kinds = [r["kind"] for r in rows]
    assert kinds == ["refund", "debit", "recharge"]
    refund = rows[0]
    assert refund["amount_minor"] == 20_000
    assert refund["service_request_id"] == req_id
    assert "Refund" in refund["description"]
    assert refund["service_status"] == "cancelled"
