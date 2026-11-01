"""Phase 0: security, team limits, money rules and SOS behaviour."""

import io

from app.livewell import email_notifications as en
from app.livewell import incident_service
from app.models.audit_log import AuditLog
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.services.notifications.alert_email import render_iot_alert_sms


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _outsider(db, seed_tenant):
    """A client and caregiver in the same agency but NOT on the test manager's team."""
    e = Elder(tenant_id=seed_tenant["tenant"].id, first_name="Other", last_name="Team", status="ACTIVE",
              phone="+919811100000")
    cg = Caregiver(tenant_id=seed_tenant["tenant"].id, first_name="Far", last_name="Away")
    db.add_all([e, cg])
    db.commit()
    return e, cg


def test_family_self_signup_is_off(client):
    res = client.post("/api/v1/auth/register-elder-portal",
                      json={"email": "x@x.example", "password": "whatever123", "phone": "9811100000"})
    assert res.status_code == 404


def test_manager_cannot_reach_other_teams(client, db, seed_tenant, auth_headers):
    other, far_cg = _outsider(db, seed_tenant)
    assert client.post(f"/api/v1/elders/{other.id}/login-as-family", headers=auth_headers).status_code == 404
    res = client.post(f"/api/v1/elders/{other.id}/portal-account", headers=auth_headers,
                      json={"email": "fam.other@x.example", "password": "familypass1"})
    assert res.status_code == 404
    assert client.get(f"/api/v1/caregivers/{far_cg.id}", headers=auth_headers).status_code == 404

    admin = _login(client, "admin@test.example")
    up = client.post("/api/v1/documents/upload", headers=admin,
                     data={"entity_type": "elder", "entity_id": str(other.id), "document_type": "LW_FAMILY_MEDICAL"},
                     files={"file": ("r.pdf", io.BytesIO(b"%PDF-1.4\n%%EOF"), "application/pdf")})
    assert up.status_code == 200, up.text
    doc_id = up.json()["id"]
    assert client.get(f"/api/v1/documents/{doc_id}", headers=auth_headers).status_code == 404
    assert client.get(f"/api/v1/documents/{doc_id}", headers=admin).status_code == 200

    row, _ = incident_service.open_incident(db, tenant_id=other.tenant_id, elder_id=other.id, kind="fall",
                                            source="device")
    assert client.get(f"/api/v1/care/incidents/{row.id}", headers=auth_headers).status_code == 404
    assert client.post(f"/api/v1/care/incidents/{row.id}/acknowledge", headers=auth_headers).status_code == 404
    summary = client.get("/api/v1/care/incidents/summary", headers=auth_headers).json()
    assert summary["total"] == 0
    assert client.get("/api/v1/care/incidents/summary", headers=admin).json()["total"] >= 1


def test_coupon_does_not_skip_approval_and_status_rules(client, db, seed_tenant, auth_headers):
    admin = _login(client, "admin@test.example")
    products = client.get("/api/v1/products", headers=admin).json()
    bar = next(p for p in products if p["name"] == "Fixed grab bar")
    client.put(f"/api/v1/products/{bar['id']}", json={"cost_paise": 100000, "margin_bp": 5000}, headers=admin)
    client.post("/api/v1/coupons", json={"code": "TINY1", "kind": "percent", "value": 100}, headers=admin)
    elder = seed_tenant["elder"]
    order = client.post("/api/v1/orders", headers=auth_headers, json={
        "elder_id": elder.id, "lines": [{"product_id": bar["id"], "qty": 1}],
        "discount_bp": 2000, "coupon_code": "TINY1", "discount_reason": "loyal",
    })
    assert order.status_code in (200, 201), order.text
    o = order.json()
    assert o["status"] == "pending_approval"  # 20% by a manager needs an admin, coupon or not

    # A manager can't push it past approval; nobody can reopen a cancelled order.
    bad = client.post(f"/api/v1/orders/{o['id']}/status", json={"status": "scheduled"}, headers=auth_headers)
    assert bad.status_code == 400
    assert client.post(f"/api/v1/orders/{o['id']}/status", json={"status": "cancelled"},
                       headers=auth_headers).status_code == 200
    again = client.post(f"/api/v1/orders/{o['id']}/status", json={"status": "approved"}, headers=admin)
    assert again.status_code == 400
    actions = {a.action for a in db.query(AuditLog).filter(AuditLog.entity_type.in_(["order", "product"])).all()}
    assert {"order_discount", "order_cancelled", "product_price"} <= actions


def test_family_sos_alerts_staff_at_once_and_family_hears_back(client, db, seed_tenant, monkeypatch):
    elder = seed_tenant["elder"]
    elder.manager_user_id = seed_tenant["manager"].id
    db.commit()
    admin = _login(client, "admin@test.example")
    client.post(f"/api/v1/team/clients/{elder.id}/family-logins", headers=admin,
                json={"email": "sos.son@family.example", "password": "familypass1"})
    fam = _login(client, "sos.son@family.example", "familypass1")

    sent = []
    monkeypatch.setattr(en, "send", lambda to, title, body, *, family, background=True: sent.append((list(to), title, family)))
    res = client.post("/api/v1/home-safety/family/sos", headers=fam, json={"note": "Amma fell"})
    assert res.status_code in (200, 201), res.text
    staff = [s for s in sent if not s[2]]
    assert staff and seed_tenant["manager"].email in staff[0][0] and staff[0][1].startswith("SOS from")

    sent.clear()
    mgr = _login(client, "manager@test.example")
    inc = client.get("/api/v1/care/incidents?status=open", headers=mgr).json()
    assert inc, "family SOS should be an open incident the manager can see"
    assert client.post(f"/api/v1/care/incidents/{inc[0]['id']}/acknowledge", headers=mgr).status_code == 200
    fam_msgs = [s for s in sent if s[2]]
    assert fam_msgs and "has seen the alert" in fam_msgs[0][1]


def test_staff_sms_is_plain_and_branded():
    text = render_iot_alert_sms(title="Wearable SOS", client_name="Lakshmi R", hub_id="hub-9",
                                mac_address="AA:BB:CC:DD:EE:FF")
    assert "LiveWell360" not in text and "AA:BB" not in text and "hub-9" not in text
    assert "ops.kushalaya.com" in text and "Lakshmi R" in text
