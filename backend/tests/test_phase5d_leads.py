"""FIX 107/108 — service areas, assessment slot + price, lead tracking, referrals, funnel."""

from app.core.security import hash_password
from app.livewell import site_settings as ss
from app.models.elder import Elder
from app.models.elder_prospect import ElderProspect
from app.models.tenant import Tenant
from app.models.user import User


def _login(client, email):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _enquire(client, **over):
    body = {"name": "Anita Rao", "phone": "+91 90000 00000", "kind": "care-check"}
    body.update(over)
    return client.post("/api/v1/home-safety/enquiries", json=body)


def _set_site(client, seed_tenant, body):
    res = client.put("/api/v1/site-settings", json=body, headers=_login(client, "admin@test.example"))
    assert res.status_code == 200, res.text
    return res.json()


def test_pincode_check_served_and_unknown(client, db, seed_tenant):
    manager = seed_tenant["manager"]
    _set_site(client, seed_tenant, {"areas": [
        {"name": "Madhapur", "pincodes": "500081, 500033", "manager_user_id": manager.id},
    ]})
    ok = client.get("/api/v1/home-safety/enquiries/pincode/500081").json()
    assert ok["served"] is True and ok["area"] == "Madhapur" and ok["message"] == "We serve your area."
    assert "manager_user_id" not in ok  # never public
    no = client.get("/api/v1/home-safety/enquiries/pincode/400001").json()
    assert no["served"] is False and "across India" in no["message"]

    res = _enquire(client, pincode="500 081")
    assert res.status_code == 200, res.text
    assert res.json()["area_served"] is True
    row = db.query(ElderProspect).order_by(ElderProspect.id.desc()).first()
    assert row.pincode == "500081" and row.area_served is True
    assert row.owner_user_id == manager.id  # area manager owns the lead


def test_bad_pincode_in_settings_rejected(client, seed_tenant):
    res = client.put(
        "/api/v1/site-settings",
        json={"areas": [{"name": "X", "pincodes": ["12"]}]},
        headers=_login(client, "admin@test.example"),
    )
    assert res.status_code == 400
    # Managers can read but not change website settings.
    res = client.put("/api/v1/site-settings", json={"city": "X"}, headers=_login(client, "manager@test.example"))
    assert res.status_code == 403


def test_utm_and_referrer_captured(client, db, seed_tenant):
    res = _enquire(
        client,
        utm_source="google",
        utm_medium="cpc",
        utm_campaign="nri-oct",
        referrer="https://www.google.com/",
        landing_page="/eldercare-discovery?utm_source=google",
    )
    assert res.status_code == 200, res.text
    row = db.query(ElderProspect).order_by(ElderProspect.id.desc()).first()
    assert (row.utm_source, row.utm_medium, row.utm_campaign) == ("google", "cpc", "nri-oct")
    assert row.referrer_url == "https://www.google.com/"
    assert row.landing_page.startswith("/eldercare-discovery")

    listed = client.get("/api/v1/prospects/elders", headers=_login(client, "admin@test.example")).json()
    mine = next(p for p in listed if p["id"] == row.id)
    assert mine["lead_source"] == "google" and mine["utm_campaign"] == "nri-oct"


def test_referral_code_attribution(client, db, seed_tenant):
    elder = seed_tenant["elder"]
    db.add(User(
        email="fam.ref@test.example", password_hash=hash_password("testpass123"),
        first_name="F", last_name="R", role="ELDER_PORTAL", tenant_id=elder.tenant_id, elder_id=elder.id,
    ))
    db.commit()
    ref = client.get("/api/v1/home-safety/family/referral", headers=_login(client, "fam.ref@test.example"))
    assert ref.status_code == 200, ref.text
    code = ref.json()["code"]
    assert ref.json()["link"].endswith(f"/r/{code}")
    assert ss.parse_referral_code(code) == elder.id
    assert ss.parse_referral_code(code[:-1] + ("A" if code[-1] != "A" else "B")) is None  # forged

    _enquire(client, ref=code.lower())
    row = db.query(ElderProspect).order_by(ElderProspect.id.desc()).first()
    assert row.referral_code == code
    listed = client.get("/api/v1/prospects/elders", headers=_login(client, "admin@test.example")).json()
    mine = next(p for p in listed if p["id"] == row.id)
    assert mine["referred_by"] == f"{elder.first_name} {elder.last_name}"
    assert mine["lead_source"] == "referral"

    # A forged code is dropped, not stored.
    _enquire(client, ref="KZZZZ1234", phone="+91 90000 00001")
    assert db.query(ElderProspect).order_by(ElderProspect.id.desc()).first().referral_code is None


def test_referral_from_other_tenant_not_attributed(client, db, seed_tenant):
    other = Tenant(name="Other", email="o@test.example", phone="1", address="a", city="c", state="s")
    db.add(other)
    db.flush()
    stranger = Elder(tenant_id=other.id, first_name="Other", last_name="Elder")
    db.add(stranger)
    db.commit()
    _enquire(client, ref=ss.referral_code(stranger.id))
    assert db.query(ElderProspect).order_by(ElderProspect.id.desc()).first().referral_code is None


def test_funnel_counts_and_scope(client, db, seed_tenant):
    tid = seed_tenant["tenant"].id
    manager = seed_tenant["manager"]
    admin = seed_tenant["admin"]

    def p(stage, owner=None, **kw):
        row = ElderProspect(tenant_id=tid, first_name="P", last_name=stage, stage=stage,
                            status="OPEN", owner_user_id=owner, **kw)
        db.add(row)
        return row

    p("NEW")
    p("CONTACTED", owner=manager.id)
    p("NEW", assessment_slot="2026-10-20 morning", utm_source="facebook")
    p("WON", owner=manager.id)
    p("ASSESSMENT_SCHEDULED", owner=admin.id)  # someone else's lead
    other = Tenant(name="Other2", email="o2@test.example", phone="1", address="a", city="c", state="s")
    db.add(other)
    db.flush()
    db.add(ElderProspect(tenant_id=other.id, first_name="X", last_name="Y", stage="WON", status="OPEN"))
    db.commit()

    f = client.get("/api/v1/prospects/funnel", headers=_login(client, "admin@test.example")).json()
    assert f["steps"] == ["NEW", "CONTACTED", "ASSESSMENT_BOOKED", "CLIENT"]
    assert f["totals"] == {"NEW": 5, "CONTACTED": 4, "ASSESSMENT_BOOKED": 3, "CLIENT": 1}  # other tenant excluded
    assert f["months"][-1]["NEW"] == 5
    assert {"source": "facebook", "count": 1} in f["sources"]

    # A care manager sees their own leads plus unassigned ones.
    m = client.get("/api/v1/prospects/funnel", headers=_login(client, "manager@test.example")).json()
    assert m["totals"] == {"NEW": 4, "CONTACTED": 3, "ASSESSMENT_BOOKED": 2, "CLIENT": 1}


def test_funnel_leaves_out_closed_leads(client, db, seed_tenant):
    tid = seed_tenant["tenant"].id
    db.add(ElderProspect(tenant_id=tid, first_name="Real", last_name="Lead", stage="NEW", status="OPEN"))
    for i in range(3):
        db.add(ElderProspect(tenant_id=tid, first_name="Test", last_name=str(i), stage="LOST", status="LOST"))
    db.commit()
    h = _login(client, "admin@test.example")
    f = client.get("/api/v1/prospects/funnel", headers=h).json()
    assert f["totals"]["NEW"] == 1 and f["excluded_closed"] == 3
    f = client.get("/api/v1/prospects/funnel?include_closed=true", headers=h).json()
    assert f["totals"]["NEW"] == 4


def test_discovery_is_free_when_unset(client, db, seed_tenant):
    site = client.get("/api/v1/home-safety/enquiries/site").json()
    assert site["assessment_price_paise"] is None
    assert site["assessment_price_label"] == "Free"
    assert site["assessment_is_paid"] is False
    assert site["testimonials"] == [] and site["trial"]["enabled"] is False
    assert "areas" in site and "pincodes" not in str(site)
    # Registered company details when nothing is typed in Settings; no GSTIN yet.
    assert site["company"]["legal_name"] == "KushAlaya Private Limited"
    assert "500039" in site["company"]["address"] and site["company"]["gstin"] == ""
    assert site["company"]["cin"] == "U88100TS2026PTC224774"

    from datetime import date, timedelta

    day = (date.today() + timedelta(days=3)).isoformat()
    res = _enquire(client, slot_date=day, slot_window="evening")
    assert res.status_code == 200, res.text
    assert res.json().get("payment") is None  # no payment step on the discovery form
    row = db.query(ElderProspect).order_by(ElderProspect.id.desc()).first()
    assert row.assessment_slot == f"{day} evening" and row.assessment_fee_paise is None
    assert row.source == "website:care-check"

    # ₹0 set by Ops is free too.
    _set_site(client, seed_tenant, {"assessment_price_paise": 0})
    assert client.get("/api/v1/home-safety/enquiries/site").json()["assessment_price_label"] == "Free"
    res = _enquire(client, slot_date=day, slot_window="morning", phone="+91 90000 00004")
    assert res.status_code == 200, res.text
    assert res.json().get("payment") is None

    bad = _enquire(client, slot_date="2001-01-01", phone="+91 90000 00002")
    assert bad.status_code == 422


def test_price_set_creates_order_and_shows_label(client, db, seed_tenant):
    _set_site(client, seed_tenant, {
        "assessment_price_paise": 149900,
        "trial": {"enabled": True, "text": "First month trial"},
        "testimonials": [{"quote": "They noticed what we missed.", "name": "Ravi K.", "place": "Kondapur"}],
        "company": {"gstin": "36abcde1234f1z5", "address": "Hyderabad"},
    })
    site = client.get("/api/v1/home-safety/enquiries/site").json()
    assert site["assessment_price_label"] == "₹1,499"
    assert site["trial"] == {"enabled": True, "text": "First month trial"}
    assert site["testimonials"][0]["name"] == "Ravi K."
    assert site["company"]["gstin"] == "36ABCDE1234F1Z5"

    from datetime import date, timedelta

    res = _enquire(client, slot_date=(date.today() + timedelta(days=2)).isoformat(), slot_window="morning")
    assert res.status_code == 200, res.text
    pay = res.json()["payment"]
    assert pay and pay["amount_minor"] == 149900
    row = db.query(ElderProspect).order_by(ElderProspect.id.desc()).first()
    assert row.assessment_order_id == pay["order_id"]

    # Enquiries without a slot never create an order.
    assert _enquire(client, phone="+91 90000 00003").json().get("payment") is None


def test_qr_source_is_recorded_and_unknown_falls_back(client, db, seed_tenant):
    assert _enquire(client, src="QR").status_code == 200
    row = db.query(ElderProspect).order_by(ElderProspect.id.desc()).first()
    assert row.source == "qr:care-check"
    assert _enquire(client, src="<script>", phone="+91 90000 00021").status_code == 200
    row = db.query(ElderProspect).order_by(ElderProspect.id.desc()).first()
    assert row.source == "website:care-check"


def test_bad_gstin_and_half_testimonial_rejected(client, seed_tenant):
    h = _login(client, "admin@test.example")
    assert client.put("/api/v1/site-settings", json={"company": {"gstin": "123"}}, headers=h).status_code == 400
    assert client.put(
        "/api/v1/site-settings", json={"testimonials": [{"quote": "Lovely", "name": ""}]}, headers=h
    ).status_code == 400


# --- audit fixes ------------------------------------------------------------------


def test_stub_payments_refused_in_production(client, db, seed_tenant, monkeypatch):
    from datetime import date, timedelta

    from app.core.config import settings
    from app.services.payments.stub_provider import StubPaymentProvider

    monkeypatch.setattr(settings, "PAYMENTS_PROVIDER", "stub")
    _set_site(client, seed_tenant, {"assessment_price_paise": 149900})
    slot = {"slot_date": (date.today() + timedelta(days=2)).isoformat(), "slot_window": "morning"}
    # Dev: the stub order is created as before.
    res = _enquire(client, phone="+91 90000 00011", **slot)
    assert res.json()["payment"]["provider"] == "stub"
    row = db.query(ElderProspect).order_by(ElderProspect.id.desc()).first()
    order_id, ref = row.assessment_order_id, res.json()["reference"]

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    res = _enquire(client, phone="+91 90000 00012", **slot)
    assert res.status_code == 200, res.text
    assert res.json().get("payment") is None and "pay at the visit" in res.json()["payment_message"]
    assert db.query(ElderProspect).order_by(ElderProspect.id.desc()).first().assessment_order_id is None
    # A stub "payment" is never accepted as paid on a live server.
    v = client.post(f"/api/v1/home-safety/enquiries/{ref}/payment",
                    json={"order_id": order_id, "payment_id": "pay_x", "signature": "x"})
    assert v.status_code == 400
    db.expire_all()
    assert db.get(ElderProspect, row.id).assessment_paid_at is None
    assert StubPaymentProvider().verify_checkout_signature(order_id="o", payment_id="p", signature="s") is False


def test_payment_reference_digits_capped(client):
    for ref in ("KA-1234567890", "99999999999999999999999", "KA-"):
        res = client.post(f"/api/v1/home-safety/enquiries/{ref}/payment",
                          json={"order_id": "o", "payment_id": "p", "signature": "s"})
        assert res.status_code == 404, (ref, res.text)


def test_referral_code_hmac_base32_and_fail_closed(monkeypatch):
    import base64
    import hashlib
    import hmac as _hmac

    from app.core.config import settings

    code = ss.referral_code(42)
    assert code.startswith("K16") and len(code) == 3 + 8
    assert set(code[3:]) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")
    assert ss.parse_referral_code(code) == 42 and ss.parse_referral_code(code.lower()) == 42
    # Old 4-hex-character codes are rejected.
    old_sig = _hmac.new((settings.SECRET_KEY or "kushalaya").encode(), b"referral:42", hashlib.sha256).hexdigest()[:4]
    assert ss.parse_referral_code("K16" + old_sig.upper()) is None
    assert base64.b32encode(_hmac.new(settings.SECRET_KEY.encode(), b"referral:42", hashlib.sha256).digest()
                            ).decode()[:8] == code[3:]
    monkeypatch.setattr(settings, "SECRET_KEY", "")
    assert ss.referral_code(42) is None
    assert ss.parse_referral_code(code) is None
