"""Android app SOS alarm: device-token registration and FCM fan-out (FCM mocked)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.rbac import ELDER_PORTAL
from app.core.security import hash_password
from app.livewell import incident_service, push, sos_siren
from app.livewell.family_care_hub import FamilyCareHubService
from app.livewell.iot_ingest_service import IotIngestService
from app.models.incident import Incident
from app.models.push_device import PushDevice
from app.models.sos_siren import SosSirenAlert
from app.models.user import User

TOKEN = "fcm-token-" + "x" * 40


def _user(db, seed_tenant, email, role, **extra) -> User:
    u = User(
        email=email,
        password_hash=hash_password("testpass123"),
        first_name=email.split("@")[0].title(),
        last_name="X",
        role=role,
        tenant_id=seed_tenant["tenant"].id,
        **extra,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _login(client, email: str) -> dict:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def sent(monkeypatch):
    """FCM configured, transport captured instead of sent."""
    out: list[dict] = []
    monkeypatch.setattr(push, "is_configured", lambda: True)
    monkeypatch.setattr(push, "_deliver", lambda messages: out.extend(messages))
    return out


def _phone(db, user, n=1):
    for i in range(n):
        push.register(db, user, f"tok-{user.id}-{i}-" + "y" * 30, app="family" if user.role == ELDER_PORTAL else "ops")


def _tokens(messages) -> set[str]:
    return {m["message"]["token"] for m in messages}


def test_register_and_unregister_device(db, client, seed_tenant):
    _user(db, seed_tenant, "fam@push.example", ELDER_PORTAL, elder_id=seed_tenant["elder"].id)
    fam = _login(client, "fam@push.example")
    assert client.post("/api/v1/push/devices", json={"token": TOKEN, "app": "family"}).status_code in (401, 403)

    res = client.post("/api/v1/push/devices", json={"token": TOKEN, "app": "family"}, headers=fam)
    assert res.status_code == 200, res.text
    row = db.query(PushDevice).filter(PushDevice.token == TOKEN).one()
    assert row.app == "family" and row.platform == "android"

    # Same phone, someone else signs in: the token moves, never duplicated.
    mgr = _login(client, "manager@test.example")
    assert client.post("/api/v1/push/devices", json={"token": TOKEN}, headers=mgr).status_code == 200
    db.expire_all()
    rows = db.query(PushDevice).filter(PushDevice.token == TOKEN).all()
    assert len(rows) == 1 and rows[0].user_id == seed_tenant["manager"].id and rows[0].app == "ops"

    # The previous user cannot remove it; the owner can.
    assert client.post("/api/v1/push/devices/unregister", json={"token": TOKEN}, headers=fam).json()["removed"] is False
    assert client.post("/api/v1/push/devices/unregister", json={"token": TOKEN}, headers=mgr).json()["removed"] is True
    db.expire_all()
    assert db.query(PushDevice).filter(PushDevice.token == TOKEN).count() == 0


def test_register_rejects_bad_app(db, client, seed_tenant):
    mgr = _login(client, "manager@test.example")
    assert client.post("/api/v1/push/devices", json={"token": TOKEN, "app": "x"}, headers=mgr).status_code == 422


def test_sos_fans_out_to_exactly_the_siren_recipients(db, seed_tenant, sent):
    elder = seed_tenant["elder"]
    son = _user(db, seed_tenant, "son@push.example", ELDER_PORTAL, elder_id=elder.id, portal_relationship="son")
    daughter = _user(db, seed_tenant, "dau@push.example", ELDER_PORTAL, elder_id=elder.id,
                     portal_relationship="daughter")
    outsider = _user(db, seed_tenant, "othermgr@push.example", "CARE_MANAGER")
    for u in (son, daughter, outsider, seed_tenant["admin"], seed_tenant["viewer"]):
        _phone(db, u)
    _phone(db, seed_tenant["manager"], n=2)  # two phones, both ring

    sos = FamilyCareHubService.raise_sos(db, son, "Help")
    row = incident_service.find_by_legacy_id(db, elder.id, sos["id"])
    unacked = {
        r.user_id for r in db.query(SosSirenAlert).filter(
            SosSirenAlert.incident_id == row.id, SosSirenAlert.acknowledged_at.is_(None))
    }
    expected = {t for (uid, toks) in push.tokens_for(db, unacked).items() for t in toks}
    assert _tokens(sent) == expected
    # Per device (27 Oct): the son who pressed gets it on his other phones too.
    assert _tokens(sent) & {t for toks in push.tokens_for(db, {son.id}).values() for t in toks}
    assert not _tokens(sent) & {t for toks in push.tokens_for(db, {outsider.id, seed_tenant["viewer"].id}).values()
                                 for t in toks}

    msg = sent[0]["message"]
    assert msg["android"]["priority"] == "HIGH"
    assert "notification" not in msg  # data-only: the app's alarm service handles it
    assert msg["data"]["type"] == "sos" and msg["data"]["reason"] == "start"
    assert all(isinstance(v, str) for v in msg["data"].values())
    # Each phone gets its own person's alert id (for Acknowledge on the lock screen).
    by_token = {m["message"]["token"]: m["message"]["data"]["alert_id"] for m in sent}
    alert_of = {r.user_id: str(r.id) for r in db.query(SosSirenAlert).filter(SosSirenAlert.incident_id == row.id)}
    for uid, toks in push.tokens_for(db, unacked).items():
        for t in toks:
            assert by_token[t] == alert_of[uid]


def test_watch_notify_family_pushes_only_the_family_and_escalation_only_heads(db, client, seed_tenant, sent):
    elder = seed_tenant["elder"]
    son = _user(db, seed_tenant, "son2@push.example", ELDER_PORTAL, elder_id=elder.id, portal_relationship="son")
    for u in (son, seed_tenant["admin"], seed_tenant["manager"]):
        _phone(db, u)

    res = IotIngestService.raise_device_sos(db, elder_id=elder.id, mac_address="aa:bb:cc:dd:ee:20")
    row = db.get(Incident, res["incident_db_id"])
    staff_tokens = {t for toks in push.tokens_for(db, {seed_tenant["admin"].id, seed_tenant["manager"].id}).values()
                    for t in toks}
    assert _tokens(sent) == staff_tokens  # verify first: family phones stay quiet
    sent.clear()

    mgr = _login(client, "manager@test.example")
    assert client.post(f"/api/v1/sos-siren/incidents/{row.id}/confirm", headers=mgr).status_code == 200
    assert _tokens(sent) == set()  # confirming alone rings nobody new
    r = client.post(f"/api/v1/sos-siren/incidents/{row.id}/notify-family", headers=mgr, json={})
    assert r.status_code == 200
    assert _tokens(sent) == set(push.tokens_for(db, {son.id})[son.id])
    assert {m["message"]["data"]["reason"] for m in sent} == {"notify_family"}


def test_escalation_rings_the_heads_again(db, seed_tenant, sent):
    elder = seed_tenant["elder"]
    son = _user(db, seed_tenant, "son3@push.example", ELDER_PORTAL, elder_id=elder.id, portal_relationship="son")
    _phone(db, seed_tenant["admin"])
    _phone(db, seed_tenant["manager"])
    sos = FamilyCareHubService.raise_sos(db, son, "Help")
    row = incident_service.find_by_legacy_id(db, elder.id, sos["id"])
    sent.clear()
    pressed = datetime.fromisoformat(sos_siren.siren(row)["pressed_at"])
    sos_siren.run_escalation(db, now=pressed + timedelta(minutes=3))
    assert _tokens(sent) == set(push.tokens_for(db, {seed_tenant["admin"].id})[seed_tenant["admin"].id])
    assert sent[0]["message"]["data"]["escalated"] == "1"


def test_not_configured_sends_nothing_and_sos_still_works(db, seed_tenant, monkeypatch):
    monkeypatch.delenv("FCM_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.delenv("FCM_SERVICE_ACCOUNT_FILE", raising=False)
    calls: list = []
    monkeypatch.setattr(push, "_deliver", lambda messages: calls.append(messages))
    elder = seed_tenant["elder"]
    son = _user(db, seed_tenant, "son4@push.example", ELDER_PORTAL, elder_id=elder.id, portal_relationship="son")
    _phone(db, seed_tenant["manager"])
    sos = FamilyCareHubService.raise_sos(db, son, "Help")
    row = incident_service.find_by_legacy_id(db, elder.id, sos["id"])
    assert not push.is_configured() and calls == []
    assert sos_siren.active_for(db, seed_tenant["manager"])[0]["incident_id"] == row.id


def test_send_all_drops_unregistered_tokens(db, seed_tenant, monkeypatch):
    _phone(db, seed_tenant["manager"], n=2)
    toks = push.tokens_for(db, {seed_tenant["manager"].id})[seed_tenant["manager"].id]
    monkeypatch.setattr(push, "service_account", lambda: {"project_id": "p", "private_key": "k", "client_email": "e"})
    monkeypatch.setattr(push, "_access_token", lambda sa: "at")

    class Res:
        def __init__(self, code, text=""):
            self.status_code, self.text = code, text

    class Client:
        def __init__(self, *a, **k):
            self.urls = []

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, json, headers):
            assert url.endswith("/projects/p/messages:send") and headers["Authorization"] == "Bearer at"
            if json["message"]["token"] == toks[0]:
                return Res(404, '{"error":{"status":"NOT_FOUND","details":[{"errorCode":"UNREGISTERED"}]}}')
            return Res(200)

    import httpx

    monkeypatch.setattr(httpx, "Client", Client)
    monkeypatch.setattr(push, "_drop_tokens", lambda dead: db.query(PushDevice).filter(
        PushDevice.token.in_(dead)).delete(synchronize_session=False))
    dead = push.send_all([push.sos_message(t, {"id": 1}, reason="start") for t in toks])
    assert dead == [toks[0]]
    assert push.tokens_for(db, {seed_tenant["manager"].id})[seed_tenant["manager"].id] == [toks[1]]
