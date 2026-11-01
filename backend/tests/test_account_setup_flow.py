"""Set-password links instead of admin-typed passwords; shared invoice links."""

from app.livewell import gst_invoices, invoice_delivery
from app.models.elder import Elder
from app.models.user import User
from app.services.account_setup import ensure_family_login, send_account_setup, setup_link


def _elder(db, tenant_id, tag="A"):
    e = Elder(tenant_id=tenant_id, first_name=f"Setup{tag}", last_name="Client", status="ACTIVE")
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def test_invite_without_password_creates_login_and_can_resend(client, admin_headers, seed_tenant, db):
    auth_headers = admin_headers
    tenant_id = seed_tenant["tenant"].id
    res = client.post(
        "/api/v1/users/invite",
        headers=auth_headers,
        json={"email": "newstaff@kushalaya.com", "first_name": "New", "last_name": "Staff",
              "role": "CARE_MANAGER", "tenant_id": tenant_id, "phone": "+91 98765 43210"},
    )
    assert res.status_code == 200, res.text
    user = db.query(User).filter(User.email == "newstaff@kushalaya.com").first()
    assert user is not None and user.password_hash  # unknown random password, not empty
    # the link is a 72 h reset token on the ops host with the welcome flag
    link = setup_link(user)
    assert link.startswith("https://ops.kushalaya.com/reset-password?token=") and link.endswith("&welcome=1")

    again = client.post(f"/api/v1/users/{user.id}/send-setup-link", headers=auth_headers)
    assert again.status_code == 200, again.text
    assert again.json()["ok"] is True and "email" in again.json()["sent"]

    assert client.post("/api/v1/users/999999/send-setup-link", headers=auth_headers).status_code == 404


def test_invite_with_password_still_works(client, admin_headers, seed_tenant):
    auth_headers = admin_headers
    res = client.post(
        "/api/v1/users/invite",
        headers=auth_headers,
        json={"email": "typed@kushalaya.com", "password": "Typed-pass-123", "first_name": "T",
              "last_name": "P", "role": "CARE_MANAGER", "tenant_id": seed_tenant["tenant"].id},
    )
    assert res.status_code == 200, res.text
    login = client.post("/api/v1/auth/login", json={"email": "typed@kushalaya.com", "password": "Typed-pass-123"})
    assert login.status_code == 200


def test_ensure_family_login_links_once_as_primary(db, seed_tenant):
    e = _elder(db, seed_tenant["tenant"].id)
    user, created = ensure_family_login(db, e, email="buyer@example.com", phone="9876543210",
                                        first_name="Buyer", last_name="One")
    db.commit()
    assert created and user.role == "ELDER_PORTAL" and user.elder_id == e.id
    from app.livewell.family_elder_access import primary_link_for_elder
    assert primary_link_for_elder(db, e.id).user_id == user.id
    same, created2 = ensure_family_login(db, e, email="BUYER@example.com", phone=None, first_name="x", last_name="y")
    assert same.id == user.id and created2 is False
    assert ensure_family_login(db, e, email="", phone="1", first_name="", last_name="") == (None, False)
    sent = send_account_setup(db, user, phone="9876543210", intro="Welcome.")
    assert sent.get("email") == "sent"


def test_plan_purchase_invoice_and_shared_link(db, client, seed_tenant):
    e = _elder(db, seed_tenant["tenant"].id, "B")
    inv = gst_invoices.issue_invoice(
        db, tenant_id=e.tenant_id, elder_id=e.id, source_type="plan_purchase", source_id="77",
        amount_paise=1200000, note="Essential plan — paid online",
    )
    db.commit()
    assert inv is not None and inv.total_paise == 1200000
    # idempotent per source
    assert gst_invoices.issue_invoice(db, tenant_id=e.tenant_id, elder_id=e.id, source_type="plan_purchase",
                                      source_id="77", amount_paise=1200000).id == inv.id
    token = invoice_delivery.share_token(inv)
    assert invoice_delivery.invoice_from_share_token(db, token).id == inv.id
    assert invoice_delivery.invoice_from_share_token(db, token + "x") is None
    pdf = client.get(f"/api/v1/business/invoices/shared/{token}")
    assert pdf.status_code == 200 and pdf.headers["content-type"].startswith("application/pdf")
    assert client.get("/api/v1/business/invoices/shared/not-a-token").status_code == 404
    # delivery with log providers never raises
    invoice_delivery.send_invoice(db, inv, to_email="buyer@example.com", to_phone="9876543210",
                                  name="Buyer One", payment_ref="pay_1", background=False)
