"""Phase 3C: band checks + Send test, family/staff notices, wording, deep links and subjects."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import hash_password
from app.livewell import email_notifications as en
from app.models.care_job import CareJob
from app.models.incident import Incident
from app.models.iot_device import IotDevice
from app.models.user import User


@pytest.fixture
def mails(monkeypatch):
    """Every email as (to, subject, text). send() runs inline so the link context is kept."""
    out: list[tuple[str, str, str]] = []
    real_send = en.send
    monkeypatch.setattr(en, "_deliver", lambda to, s, t, h: out.extend((x, s, t) for x in to))
    monkeypatch.setattr(
        en, "send", lambda to, title, body, *, family, background=True: real_send(to, title, body, family=family, background=False)
    )
    return out


@pytest.fixture
def family(db, seed_tenant):
    elder = seed_tenant["elder"]
    elder.manager_user_id = seed_tenant["manager"].id
    u = User(email="fam3c@test.example", password_hash=hash_password("testpass123"), first_name="Fam",
             last_name="C", role="ELDER_PORTAL", tenant_id=elder.tenant_id, elder_id=elder.id)
    db.add(u)
    db.commit()
    return u


def _to(mails, addr):
    return [(s, t) for to, s, t in mails if to == addr]


def test_new_event_keys_and_defaults(db, seed_tenant):
    rules = en.get_rules(None)
    for key in ("request_cancelled", "approval", "device"):
        assert key in rules["staff"]
    assert rules["staff"]["approval"]["manager"] is False and rules["staff"]["approval"]["admins"] is True
    assert rules["staff"]["device"]["admins"] is False
    assert {"safety", "order"} <= set(rules["family"])


def test_subject_names_client_and_link_is_deep(db, seed_tenant, family, mails):
    elder = seed_tenant["elder"]
    name = f"{elder.first_name} {elder.last_name}".strip()
    en.email_staff(db, elder, "visit_done", "Visit completed", "Done.")
    subj, text = _to(mails, "manager@test.example")[0]
    assert subj == f"KushAlaya: Visit completed — {name}"
    assert f"{en.OPS_URL}/kushalaya/customers/{elder.id}" in text
    mails.clear()
    en.email_family(db, elder, "reply", "Reply from your care team", "Hi", path="/messages")
    subj, text = _to(mails, "fam3c@test.example")[0]
    assert elder.first_name in subj and f"{en.FAMILY_URL}/messages" in text


def test_missed_visit_wording(db, seed_tenant, family, mails):
    from app.livewell.care_jobs import _missed_notices

    elder = seed_tenant["elder"]
    job = CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, kind="visit", title="Care visit", status="missed",
                  scheduled_at=datetime(2026, 10, 6, 2, 30, tzinfo=timezone.utc))
    db.add(job)
    db.commit()
    _missed_notices(db, elder, job)
    staff = _to(mails, "manager@test.example")[0][1]
    assert "Tue 6 Oct, 8:00 AM IST" in staff and "Next:" in staff and "has been told" in staff
    assert f"{en.OPS_URL}/kushalaya/visits" in staff
    fam = _to(mails, "fam3c@test.example")[0][1]
    assert "sorry" in fam.lower() and "will call you" in fam and f"{en.FAMILY_URL}/schedule" in fam


def test_ops_completion_tells_family_with_date(db, seed_tenant, family, mails):
    from app.livewell.care_jobs import update_job

    elder = seed_tenant["elder"]
    job = CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, kind="visit", title="Care visit",
                  status="checked_in", scheduled_at=datetime.now(timezone.utc))
    db.add(job)
    db.commit()
    update_job(db, seed_tenant["manager"], job.id, {"status": "completed"})
    fam = _to(mails, "fam3c@test.example")
    assert fam and "completed on" in fam[0][1] and "IST" in fam[0][1]


def test_request_confirm_and_cancel(db, seed_tenant, family, mails):
    from app.livewell.family_service_requests import FamilyServiceRequestService as S

    elder = seed_tenant["elder"]
    pref = datetime(2030, 1, 3, 5, 0, tzinfo=timezone.utc).isoformat()  # Thu 3 Jan 10:30 IST
    req = S.create_for_family(db, family, service_type="haircut_grooming", preferred_at=pref, notes="")
    mails.clear()
    S.staff_update(db, seed_tenant["admin"], elder.id, req["id"], status="confirmed", staff_note="Barber booked")
    fam = _to(mails, "fam3c@test.example")
    assert fam and "Thu 3 Jan, 10:30 AM IST" in fam[0][1] and "Barber booked" in fam[0][1]
    assert f"{en.FAMILY_URL}/services" in fam[0][1]

    req2 = S.create_for_family(db, family, service_type="grocery_errand", preferred_at=pref, notes="")
    mails.clear()
    S.cancel_for_family(db, family, req2["id"])  # never booked: staff still told
    staff = _to(mails, "manager@test.example")
    assert staff and staff[0][0].startswith("KushAlaya: Family cancelled") and "not been booked" in staff[0][1]


def test_failed_family_email_does_not_fail_update(db, seed_tenant, family, monkeypatch):
    from app.livewell.family_service_requests import FamilyServiceRequestService as S

    def boom(*a, **k):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(en, "send", boom)
    req = S.create_for_family(db, family, service_type="haircut_grooming", preferred_at=None, notes="")
    out = S.staff_update(db, seed_tenant["admin"], seed_tenant["elder"].id, req["id"], status="declined")
    assert out["status"] == "declined"


def _login(client, email):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_discount_approval_email_and_order_notices(client, db, seed_tenant, family, mails, auth_headers):
    admin = _login(client, "admin@test.example")
    p = client.get("/api/v1/products", headers=admin).json()[0]
    client.put(f"/api/v1/products/{p['id']}", json={"cost_paise": 100000, "margin_bp": 3000}, headers=admin)
    elder_id = seed_tenant["elder"].id
    res = client.post("/api/v1/orders", headers=auth_headers,
                      json={"elder_id": elder_id, "lines": [{"product_id": p["id"]}], "discount_bp": 2000})
    assert res.json()["status"] == "pending_approval"
    approval = _to(mails, "admin@test.example")
    assert approval and approval[0][0].startswith("KushAlaya: Discount to approve")
    assert f"/kushalaya/customers/{elder_id}?tab=orders" in approval[0][1]
    assert not _to(mails, "manager@test.example")  # the manager asked; admins approve

    o = client.post("/api/v1/orders", headers=admin,
                    json={"elder_id": elder_id, "lines": [{"product_id": p["id"]}]}).json()
    client.post(f"/api/v1/orders/{o['id']}/status", headers=admin, json={"status": "quoted"})
    mails.clear()
    client.post(f"/api/v1/orders/{o['id']}/status", headers=admin, json={"status": "cancelled"})
    fam = _to(mails, "fam3c@test.example")
    assert fam and "Order cancelled" in fam[0][0] and "cancelled on" in fam[0][1]


def test_hazard_tells_family(db, seed_tenant, family, mails):
    from app.livewell.visit_reports import add_hazard

    add_hazard(db, seed_tenant["elder"], note="Loose rug in the hall", product_id=None, job_id=None, by="Ravi")
    fam = _to(mails, "fam3c@test.example")
    assert fam and "Safety concern" in fam[0][0] and "Loose rug" in fam[0][1] and "/safety" in fam[0][1]


def _band(db, elder, mac="AA:BB:CC:DD:EE:01", **kw):
    d = IotDevice(tenant_id=elder.tenant_id, elder_id=elder.id, mac_address=mac, status="active", **kw)
    db.add(d)
    db.commit()
    return d


def test_band_checks_once_per_day(db, seed_tenant, family, mails):
    from app.livewell.band_checks import check_bands

    elder = seed_tenant["elder"]
    now = datetime(2026, 10, 6, 6, 0, tzinfo=timezone.utc)  # 11:30 IST
    off = _band(db, elder, last_seen_at=now - timedelta(hours=3), battery_level=80)
    keys = check_bands(db, now=now)
    assert keys == [f"auto:device_offline:{off.id}:2026-10-06"]
    assert check_bands(db, now=now + timedelta(minutes=2)) == []  # every 2 min: no repeat
    staff = _to(mails, "manager@test.example")
    assert staff and "Band offline" in staff[0][0] and "?tab=devices" in staff[0][1]
    assert not _to(mails, "admin@test.example")  # device emails: manager by default
    # Resolved the same day and still offline: stays quiet until tomorrow.
    db.query(Incident).update({"status": "resolved"})
    db.commit()
    assert check_bands(db, now=now + timedelta(hours=1)) == []
    assert len(check_bands(db, now=now + timedelta(days=1))) == 1
    # Night: nothing.
    assert check_bands(db, now=datetime(2026, 10, 7, 18, 0, tzinfo=timezone.utc)) == []


def test_band_low_battery(db, seed_tenant):
    from app.livewell.band_checks import check_bands

    elder = seed_tenant["elder"]
    now = datetime(2026, 10, 6, 6, 0, tzinfo=timezone.utc)
    b = _band(db, elder, last_seen_at=now - timedelta(minutes=5), battery_level=12)
    assert check_bands(db, now=now) == [f"auto:battery_low:{b.id}:2026-10-06"]
    inc = db.query(Incident).filter(Incident.kind == "battery_low").one()
    assert "12%" in inc.note and b.mac_address not in inc.note  # family-facing: no device IDs


def test_send_test_and_replace_band(client, db, seed_tenant, auth_headers, mails):
    elder = seed_tenant["elder"]
    elder.manager_user_id = seed_tenant["manager"].id
    b = _band(db, elder, last_seen_at=datetime.now(timezone.utc), battery_level=55)
    res = client.post(f"/api/v1/iot/devices/{b.id}/test", headers=auth_headers)
    assert res.status_code == 200, res.text
    assert "manager@test.example" in res.json()["sent_to"]
    subj, text = _to(mails, "manager@test.example")[0]
    assert subj.startswith("KushAlaya: Test alert") and b.mac_address in text
    assert db.query(Incident).count() == 0  # a test opens nothing

    res = client.put("/api/v1/iot/devices/mac", headers=auth_headers,
                     json={"elder_id": elder.id, "device_id": b.id, "mac_address": "AA:BB:CC:DD:EE:99"})
    assert res.status_code == 200, res.text
    assert res.json()["battery_level"] is None and res.json()["last_seen_at"] is None


def test_band_offline_is_per_device(db, seed_tenant):
    """One band's open alert must not hide a second band going offline on the same client."""
    from app.livewell.band_checks import check_bands

    elder = seed_tenant["elder"]
    now = datetime(2026, 10, 6, 6, 0, tzinfo=timezone.utc)
    a = _band(db, elder, last_seen_at=now - timedelta(hours=3), battery_level=80)
    assert check_bands(db, now=now) == [f"auto:device_offline:{a.id}:2026-10-06"]
    b = _band(db, elder, mac="AA:BB:CC:DD:EE:02", last_seen_at=now - timedelta(hours=3), battery_level=80)
    assert check_bands(db, now=now + timedelta(minutes=2)) == [f"auto:device_offline:{b.id}:2026-10-06"]
    macs = {i.device_mac for i in db.query(Incident).filter(Incident.kind == "device_offline").all()}
    assert macs == {a.mac_address, b.mac_address}
    assert check_bands(db, now=now + timedelta(minutes=4)) == []


def test_reassessment_digest_date_is_ist():
    from app.livewell.daily_checks import _ist_date

    # 20:00 UTC on 5 Oct is 01:30 IST on 6 Oct.
    assert _ist_date("2026-10-05T20:00:00+00:00") == "2026-10-06"
    assert _ist_date("2026-10-05T20:00:00") == "2026-10-06"
