"""Team alerts: rules, WhatsApp recipients, stuck leads, and the vendor owner."""

from datetime import datetime, timedelta, timezone

from app.livewell import email_notifications as en
from app.livewell import team_alerts
from app.models.elder_prospect import ElderProspect
from app.models.tenant import Tenant
from app.models.user import User

NOON_IST = datetime(2026, 11, 6, 6, 30, tzinfo=timezone.utc)
UTC_NOW = NOON_IST.replace(tzinfo=None)


def _capture(monkeypatch):
    sent = {"email": [], "whatsapp": []}
    monkeypatch.setattr(en, "send", lambda to, title, body, **kw: sent["email"].append((sorted(to), title, body)))
    monkeypatch.setattr(team_alerts, "_send_whatsapp", lambda phones, text: sent["whatsapp"].append((phones, text)))
    return sent


def _lead(db, tid, age_days, stage="NEW", name="Asha"):
    row = ElderProspect(tenant_id=tid, first_name=name, last_name="Rao", stage=stage, phone="9000000000")
    db.add(row)
    db.commit()
    row.created_at = UTC_NOW - timedelta(days=age_days)
    db.commit()
    return row


def _tid(seed_tenant):
    return seed_tenant["tenant"].id


def _give_admin_a_phone(db, tid):
    admin = db.query(User).filter(User.tenant_id == tid, User.role == "TENANT_ADMIN").first()
    admin.phone = "9876543210"
    db.commit()
    return admin


def test_defaults_are_admins_with_whatsapp(db, seed_tenant):
    rules = en.get_rules(db.get(Tenant, _tid(seed_tenant)))
    for key in ("lead_new", "assessment_booked", "assessment_done", "vendor_new", "lead_stuck"):
        rule = rules["staff"][key]
        assert rule["enabled"] and rule["admins"] and rule["whatsapp"] and not rule["manager"]
    assert rules["staff"]["visit_done"]["whatsapp"] is False
    assert rules["lead_stuck"]["repeat_days"] == 2
    assert rules["lead_stuck"]["days"]["NEW"] == 3 and "WON" not in rules["lead_stuck"]["days"]


def test_extra_person_gets_email_and_whatsapp(db, seed_tenant, monkeypatch):
    tid = _tid(seed_tenant)
    sent = _capture(monkeypatch)
    _give_admin_a_phone(db, tid)
    chandan = User(tenant_id=tid, email="chandan@test.example", first_name="C", last_name="G",
                   password_hash="x", role="CARE_MANAGER", phone="8000000000")
    db.add(chandan)
    db.commit()
    en.save_rules(db, db.get(Tenant, tid), {"staff": {"vendor_new": {"extra": [chandan.email]}}})
    team_alerts.alert_team(db, tid, "vendor_new", "New vendor", "Sri Sai", background=False)
    assert chandan.email in sent["email"][0][0]
    assert sent["whatsapp"][0][0] == ["918000000000", "919876543210"]
    assert "New vendor. Sri Sai" in sent["whatsapp"][0][1]


def test_switched_off_sends_nothing(db, seed_tenant, monkeypatch):
    tid = _tid(seed_tenant)
    sent = _capture(monkeypatch)
    en.save_rules(db, db.get(Tenant, tid), {"staff": {"vendor_new": {"enabled": False}}})
    team_alerts.alert_team(db, tid, "vendor_new", "New vendor", "x", background=False)
    assert sent == {"email": [], "whatsapp": []}


def test_stuck_lead_alerts_once_then_every_two_days(db, seed_tenant, monkeypatch):
    tid = _tid(seed_tenant)
    sent = _capture(monkeypatch)
    _lead(db, tid, 0, name="Fresh")
    stuck = _lead(db, tid, 5, name="Stuck")
    _lead(db, tid, 30, stage="WON", name="Done")
    assert team_alerts.run_stuck_lead_alerts(db, NOON_IST) == 1
    assert "Stuck Rao (New, 5 days)" in sent["email"][0][2]
    assert "Fresh" not in sent["email"][0][2] and "Done" not in sent["email"][0][2]
    assert team_alerts.run_stuck_lead_alerts(db, NOON_IST + timedelta(days=1)) == 0
    assert team_alerts.run_stuck_lead_alerts(db, NOON_IST + timedelta(days=2)) == 1
    db.refresh(stuck)
    assert stuck.stage_alerted_at is not None


def test_many_stuck_leads_make_one_message(db, seed_tenant, monkeypatch):
    tid = _tid(seed_tenant)
    sent = _capture(monkeypatch)
    for i in range(25):
        _lead(db, tid, 10, name=f"L{i}")
    assert team_alerts.run_stuck_lead_alerts(db, NOON_IST) == 25
    assert len(sent["email"]) == 1 and "and 5 more" in sent["email"][0][2]


def test_stuck_alerts_wait_for_the_working_day(db, seed_tenant, monkeypatch):
    tid = _tid(seed_tenant)
    _capture(monkeypatch)
    _lead(db, tid, 10)
    night = datetime(2026, 11, 6, 20, 0, tzinfo=timezone.utc)  # 01:30 IST
    assert team_alerts.run_stuck_lead_alerts(db, night) == 0


def test_days_can_be_changed_per_phase(db, seed_tenant, monkeypatch):
    tid = _tid(seed_tenant)
    _capture(monkeypatch)
    en.save_rules(db, db.get(Tenant, tid), {"lead_stuck": {"days": {"NEW": 7}, "repeat_days": 4}})
    rules = en.get_rules(db.get(Tenant, tid))["lead_stuck"]
    assert rules["days"]["NEW"] == 7 and rules["repeat_days"] == 4 and rules["days"]["FOLLOW_UP_1"] == 3
    _lead(db, tid, 5)
    assert team_alerts.run_stuck_lead_alerts(db, NOON_IST) == 0


def test_new_lead_and_vendor_alert(client, db, seed_tenant, admin_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(team_alerts, "alert_team", lambda db, tid, event, title, body, **kw: calls.append(event))
    res = client.post("/api/v1/sales/leads", headers=admin_headers, json={"name": "Asha Rao", "phone": "9000000001"})
    assert res.status_code == 201, res.text
    res = client.post("/api/v1/vendors", headers=admin_headers, json={"company_name": "Sri Sai", "phone1": "9876543210"})
    assert res.status_code == 201, res.text
    assert calls == ["lead_new", "vendor_new"]


def test_vendor_owner_and_added_by(client, db, seed_tenant, admin_headers, auth_headers):
    me = client.get("/api/v1/auth/me", headers=admin_headers).json()
    manager = client.get("/api/v1/auth/me", headers=auth_headers).json()
    body = {"company_name": "Sri Sai", "phone1": "9876543210"}
    v = client.post("/api/v1/vendors", headers=admin_headers, json=body).json()
    assert v["owner_user_id"] == me["id"] and v["added_by_name"] and v["owner_staff_name"] == v["added_by_name"]

    staff = client.get("/api/v1/vendors/options", headers=admin_headers).json()["staff"]
    assert manager["id"] in [s["id"] for s in staff]

    url = f"/api/v1/vendors/{v['id']}"
    moved = client.put(url, headers=admin_headers, json={**body, "owner_user_id": manager["id"]}).json()
    assert moved["owner_user_id"] == manager["id"]
    # Saving without an owner keeps the current one.
    assert client.put(url, headers=admin_headers, json=body).json()["owner_user_id"] == manager["id"]
    # An owner must be our own staff.
    assert client.put(url, headers=admin_headers, json={**body, "owner_user_id": 999999}).status_code == 422
