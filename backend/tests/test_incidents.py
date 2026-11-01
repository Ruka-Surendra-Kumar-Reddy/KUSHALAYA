"""Staff-side SOS / incident operations: dedupe, collapse, lifecycle, escalation, API auth."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.rbac import ELDER_PORTAL
from app.core.security import hash_password
from app.livewell import incident_service, sos_siren
from app.livewell.family_care_hub import FamilyCareHubService
from app.livewell.iot_ingest_service import IotIngestService
from app.models.elder import Elder
from app.models.incident import Incident, IncidentEvent
from app.models.user import User


def _elder(db, seed_tenant, first="Sos", last="Senior") -> Elder:
    elder = Elder(
        tenant_id=seed_tenant["tenant"].id,
        first_name=first,
        last_name=last,
        status="ACTIVE",
        manager_user_id=seed_tenant["manager"].id,
    )
    db.add(elder)
    db.commit()
    db.refresh(elder)
    return elder


def _family_user(db, elder: Elder, tag: str = "") -> User:
    user = User(
        email=f"family.inc{tag}.{elder.id}@example.com",
        password_hash=hash_password("demo1234"),
        first_name="Family",
        last_name="Inc",
        role=ELDER_PORTAL,
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
        portal_relationship="self",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _hub(db, elder: Elder) -> dict:
    db.refresh(elder)
    return (elder.custom_attributes or {}).get("safe_home", {}).get("family_hub", {})


def _events(db, incident_id: int) -> list[IncidentEvent]:
    return incident_service.list_events(db, incident_id)


# ---------------------------------------------------------------------------
# Dedupe / collapse
# ---------------------------------------------------------------------------


def test_sos_dedupe_key_folds_repeat_into_open_incident(db, seed_tenant):
    elder = _elder(db, seed_tenant)
    first = IotIngestService.raise_device_sos(
        db, elder_id=elder.id, mac_address="aa:bb:cc:dd:ee:01", dedupe_key="aa:bb:cc:dd:ee:01:SOS_BUTTON"
    )
    second = IotIngestService.raise_device_sos(
        db, elder_id=elder.id, mac_address="aa:bb:cc:dd:ee:01", dedupe_key="aa:bb:cc:dd:ee:01:SOS_BUTTON"
    )
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert second["incident_db_id"] == first["incident_db_id"]
    assert second["id"] == first["id"]  # legacy id of the open incident, not a new one

    rows = db.query(Incident).filter(Incident.elder_id == elder.id).all()
    assert len(rows) == 1
    assert rows[0].kind == "sos_button" and rows[0].severity == "critical" and rows[0].status == "open"
    events = _events(db, rows[0].id)
    assert [e.event for e in events].count("received") == 2
    assert any("duplicate suppressed" in (e.detail or "") for e in events)

    # Care team first (29 Oct): the family hub stays quiet until staff confirm and notify.
    assert not [i for i in _hub(db, elder).get("incidents") or [] if i.get("kind") == "sos"]
    sos_siren.confirm(db, rows[0].id, seed_tenant["manager"])
    assert not [i for i in _hub(db, elder).get("incidents") or [] if i.get("kind") == "sos"]
    sos_siren.notify_family(db, rows[0].id, seed_tenant["manager"])
    hub = _hub(db, elder)
    assert len([i for i in hub["incidents"] if i.get("kind") == "sos"]) == 1
    assert len([a for a in hub["alerts"] if a.get("severity") == "critical"]) == 1


def test_sos_dedupe_window_expires(db, seed_tenant):
    elder = _elder(db, seed_tenant)
    now = datetime.now(timezone.utc)
    a, created_a = incident_service.open_incident(
        db,
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
        kind="sos_button",
        dedupe_key="mac:SOS",
        now=now - timedelta(seconds=120),
        dedupe_window_seconds=65,
    )
    b, created_b = incident_service.open_incident(
        db,
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
        kind="sos_button",
        dedupe_key="mac:SOS",
        now=now,
        dedupe_window_seconds=65,
    )
    assert created_a and created_b
    assert a.id != b.id


def test_device_offline_never_stacks_and_pushes_one_family_alert(db, seed_tenant):
    elder = _elder(db, seed_tenant)
    ids = set()
    for _ in range(5):
        res = IotIngestService.raise_device_event(
            db, event_type="DEVICE_OFFLINE", elder_id=elder.id, mac_address="aa:bb:cc:dd:ee:02"
        )
        ids.add(res["incident_db_id"])
    assert len(ids) == 1
    (incident_id,) = ids
    rows = db.query(Incident).filter(Incident.elder_id == elder.id, Incident.kind == "device_offline").all()
    assert len(rows) == 1
    received = [e for e in _events(db, incident_id) if e.event == "received"]
    assert len(received) == 5
    assert sum(1 for e in received if "repeat" in (e.detail or "")) == 4

    hub = _hub(db, elder)
    assert len([i for i in hub["incidents"] if i.get("kind") == "device_offline"]) == 1
    assert len([a for a in hub["alerts"] if "offline" in (a.get("title") or "").lower() or "not heard" in (a.get("title") or "").lower() or "not checking in" in (a.get("title") or "").lower()]) == 1


def test_device_offline_reopens_after_resolution(db, seed_tenant):
    elder = _elder(db, seed_tenant)
    first = IotIngestService.raise_device_event(db, event_type="DEVICE_OFFLINE", elder_id=elder.id)
    row = incident_service.get_incident(db, first["incident_db_id"])
    incident_service.resolve(db, row, outcome="device_issue", note="charged", user=seed_tenant["manager"])
    second = IotIngestService.raise_device_event(db, event_type="DEVICE_OFFLINE", elder_id=elder.id)
    assert second["duplicate"] is False
    assert second["incident_db_id"] != first["incident_db_id"]


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_ack_then_resolve_chain_writes_events_and_mirrors_json(db, seed_tenant):
    elder = _elder(db, seed_tenant)
    manager = seed_tenant["manager"]
    res = IotIngestService.raise_device_sos(db, elder_id=elder.id, mac_address="aa:bb:cc:dd:ee:03")
    row = incident_service.get_incident(db, res["incident_db_id"], tenant_id=elder.tenant_id)
    assert row.status == "open" and row.legacy_id == res["id"]

    incident_service.acknowledge(db, row, manager)
    assert row.status == "acknowledged"
    assert row.acknowledged_by_user_id == manager.id
    assert row.acknowledged_at is not None
    # Watch SOS: staff confirm it, then tell the family (29 Oct).
    sos_siren.confirm(db, row.id, manager)
    sos_siren.notify_family(db, row.id, manager)

    incident_service.add_note(db, row, manager, "Called daughter, on her way")

    incident_service.resolve(db, row, outcome="contacted_family", note="Daughter arrived", user=manager)
    assert row.status == "resolved"
    assert row.outcome == "contacted_family"
    assert row.resolved_by_user_id == manager.id

    kinds = [e.event for e in _events(db, row.id)]
    assert kinds[0] == "received"
    assert "acknowledged" in kinds and "note" in kinds and kinds[-1] == "resolved"
    assert kinds.index("acknowledged") < kinds.index("note") < kinds.index("resolved")

    # JSON mirror: legacy incident resolved and its alert marked read.
    hub = _hub(db, elder)
    legacy = next(i for i in hub["incidents"] if i["id"] == res["id"])
    assert legacy["status"] == "resolved"
    assert legacy["resolved_by"] == "Test Manager"  # a name, never the email (batch B #6)
    linked = [a for a in hub["alerts"] if a.get("incident_id") == res["id"]]
    assert linked and all(a.get("read_at") for a in linked)


def test_resolve_validation(db, seed_tenant):
    from workforceos_core.exceptions import WorkforceHTTPError as HTTPException

    elder = _elder(db, seed_tenant)
    manager = seed_tenant["manager"]
    row, _ = incident_service.open_incident(db, tenant_id=elder.tenant_id, elder_id=elder.id, kind="fall")
    with pytest.raises(HTTPException):
        incident_service.resolve(db, row, outcome="", user=manager)
    with pytest.raises(HTTPException):
        incident_service.resolve(db, row, outcome="other", note="", user=manager)
    with pytest.raises(HTTPException):
        incident_service.resolve(db, row, outcome="family_resolved", user=manager)  # staff may not
    with pytest.raises(HTTPException):
        incident_service.resolve(db, row, outcome="not_a_thing", user=manager)
    incident_service.resolve(db, row, outcome="other", note="Neighbour checked in", user=manager)
    assert row.status == "resolved" and row.resolution_note == "Neighbour checked in"
    with pytest.raises(HTTPException):
        incident_service.acknowledge(db, row, manager)


def test_family_read_no_longer_resolves_but_family_resolve_does(db, seed_tenant):
    elder = _elder(db, seed_tenant)
    family = _family_user(db, elder)
    sos = FamilyCareHubService.raise_sos(db, family, "Please call")
    row = incident_service.find_by_legacy_id(db, elder.id, sos["id"])
    assert row is not None and row.kind == "family_sos" and row.source == "family"

    # The person who raised it doesn't get an alert about their own SOS; a sibling does.
    sibling = _family_user(db, elder, tag="2")
    # Care team first (29 Oct): the sibling hears once staff confirm and notify the family.
    assert FamilyCareHubService.list_alerts(db, sibling) == []
    sos_siren.confirm(db, row.id, seed_tenant["manager"])
    sos_siren.notify_family(db, row.id, seed_tenant["manager"])
    assert not any(a["severity"] == "critical" for a in FamilyCareHubService.list_alerts(db, family))
    alert = next(a for a in FamilyCareHubService.list_alerts(db, sibling) if a["severity"] == "critical")
    FamilyCareHubService.mark_alert_read(db, sibling, alert["id"])
    db.refresh(row)
    assert row.status == "acknowledged"  # confirmed by staff, not resolved by the read
    assert any(e.event == "note" and "family acknowledged alert" in (e.detail or "") for e in _events(db, row.id))
    legacy = next(i for i in FamilyCareHubService.list_incidents(db, family) if i["id"] == sos["id"])
    assert legacy["status"] == "open"

    FamilyCareHubService.resolve_incident(db, family, sos["id"], status="resolved")
    db.refresh(row)
    assert row.status == "resolved"
    assert row.outcome == "family_resolved"
    assert row.resolved_by_label == "Family Inc (family)"  # a name, never the email (batch B #6)
    legacy = next(i for i in FamilyCareHubService.list_incidents(db, family) if i["id"] == sos["id"])
    assert legacy["status"] == "resolved"


# ---------------------------------------------------------------------------
# Notification recording
# ---------------------------------------------------------------------------


class _FakeEmail:
    def __init__(self):
        self.sent: list[str] = []

    def send(self, *, to, subject, body, html=None):
        from app.services.notifications.types import DeliveryResult, DeliveryStatus

        self.sent.append(to)
        if to.startswith("bad@"):
            return DeliveryResult(status=DeliveryStatus.FAILED, detail="mailbox full")
        return DeliveryResult(status=DeliveryStatus.SENT)


def test_ingest_records_notification_outcomes_per_recipient(db, seed_tenant, monkeypatch):
    from app.core.config import settings

    elder = _elder(db, seed_tenant)
    fake = _FakeEmail()
    monkeypatch.setattr(settings, "NOTIFICATION_EMAIL_PROVIDER", "smtp")
    monkeypatch.setattr(settings, "SMTP_ALERT_TO", "ops@kushalaya.test, bad@kushalaya.test")
    monkeypatch.setattr(incident_service, "get_email_provider", lambda: fake)

    res = IotIngestService.raise_device_sos(db, elder_id=elder.id)
    notified = [e for e in _events(db, res["incident_db_id"]) if e.event == "notified"]
    by_recipient = {e.recipient: e for e in notified if e.channel == "email"}
    # A watch SOS also emails the client's staff (manager / admins) while it waits to be verified.
    assert {"ops@kushalaya.test", "bad@kushalaya.test"} <= set(by_recipient)
    assert by_recipient["ops@kushalaya.test"].ok is True
    assert by_recipient["bad@kushalaya.test"].ok is False
    assert "mailbox full" in (by_recipient["bad@kushalaya.test"].detail or "")


def test_ingest_records_skipped_channel_when_provider_unconfigured(db, seed_tenant, monkeypatch):
    from app.core.config import settings

    elder = _elder(db, seed_tenant)
    monkeypatch.setattr(settings, "NOTIFICATION_EMAIL_PROVIDER", "log")
    monkeypatch.setattr(settings, "SMTP_ALERT_TO", "ops@kushalaya.test")
    res = IotIngestService.raise_device_sos(db, elder_id=elder.id)
    notified = [e for e in _events(db, res["incident_db_id"]) if e.event == "notified" and e.channel == "email"]
    assert len(notified) == 1 and notified[0].ok is False and "not configured" in (notified[0].detail or "")


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------


def test_escalation_levels_by_elapsed_time(db, seed_tenant, monkeypatch):
    from app.core.config import settings

    elder = _elder(db, seed_tenant)
    fake = _FakeEmail()
    monkeypatch.setattr(settings, "NOTIFICATION_EMAIL_PROVIDER", "smtp")
    monkeypatch.setattr(settings, "SMTP_ALERT_TO", "ops@kushalaya.test")
    monkeypatch.setattr(incident_service, "get_email_provider", lambda: fake)

    t0 = datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc)
    row, _ = incident_service.open_incident(db, tenant_id=elder.tenant_id, elder_id=elder.id, kind="sos_button", now=t0)

    # 4 min: nothing yet.
    out = incident_service.run_escalation_scan(db, now=t0 + timedelta(minutes=4), tenant_id=elder.tenant_id)
    assert out["escalated_count"] == 0
    db.refresh(row)
    assert row.escalation_level == 0 and row.status == "open"

    # 5 min: level 1 → tenant care managers / admins get email (seed users are @test.example → filtered).
    out = incident_service.run_escalation_scan(db, now=t0 + timedelta(minutes=5), tenant_id=elder.tenant_id)
    assert out["escalated_count"] == 1 and out["escalated"][0]["level"] == 1
    db.refresh(row)
    assert row.escalation_level == 1 and row.status == "open"
    assert row.escalated_at is not None

    # Same tick again: idempotent.
    out = incident_service.run_escalation_scan(db, now=t0 + timedelta(minutes=6), tenant_id=elder.tenant_id)
    assert out["escalated_count"] == 0

    # 10 min: level 2 → SMTP_ALERT_TO.
    fake.sent.clear()
    incident_service.run_escalation_scan(db, now=t0 + timedelta(minutes=10), tenant_id=elder.tenant_id)
    db.refresh(row)
    assert row.escalation_level == 2 and row.status == "open"
    assert fake.sent == ["ops@kushalaya.test"]

    # 20 min: level 3 → repeat level 2 and mark escalated.
    fake.sent.clear()
    incident_service.run_escalation_scan(db, now=t0 + timedelta(minutes=20), tenant_id=elder.tenant_id)
    db.refresh(row)
    assert row.escalation_level == 3 and row.status == "escalated"
    assert fake.sent == ["ops@kushalaya.test"]

    escalations = [e for e in _events(db, row.id) if e.event == "escalated"]
    assert [int(e.detail.split()[1]) for e in escalations] == [1, 2, 3]
    notified = [e for e in _events(db, row.id) if e.event == "notified"]
    assert len(notified) >= 2  # one per level-2/3 email at minimum


def test_acknowledged_incident_does_not_escalate(db, seed_tenant):
    elder = _elder(db, seed_tenant)
    t0 = datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc)
    row, _ = incident_service.open_incident(db, tenant_id=elder.tenant_id, elder_id=elder.id, kind="sos_button", now=t0)
    incident_service.acknowledge(db, row, seed_tenant["manager"], now=t0 + timedelta(minutes=1))
    out = incident_service.run_escalation_scan(db, now=t0 + timedelta(minutes=30), tenant_id=elder.tenant_id)
    assert out["escalated_count"] == 0
    db.refresh(row)
    assert row.escalation_level == 0 and row.status == "acknowledged"


def test_escalation_policy_override_from_app_setting(db, seed_tenant):
    from app.models.app_global_setting import AppGlobalSetting

    tenant_id = seed_tenant["tenant"].id
    assert incident_service.escalation_policy(db, tenant_id) == {"ack_minutes": 5, "level2_minutes": 10, "level3_minutes": 20}
    db.add(
        AppGlobalSetting(
            key=incident_service.ESCALATION_SETTINGS_KEY,
            value={"ack_minutes": 3, "tenants": {str(tenant_id): {"level3_minutes": 12}}},
        )
    )
    db.commit()
    policy = incident_service.escalation_policy(db, tenant_id)
    assert policy == {"ack_minutes": 3, "level2_minutes": 10, "level3_minutes": 12}
    assert incident_service.target_level_for_elapsed(3, policy) == 1
    assert incident_service.target_level_for_elapsed(12, policy) == 3


def test_job_handler_registered_and_runs(db, seed_tenant):
    import app.jobs.handlers as handlers
    from workforceos_core.jobs.registry import known_job_types, run_handler

    assert handlers.JOB_INCIDENT_ESCALATION_SCAN in known_job_types()
    out = run_handler(db, handlers.JOB_INCIDENT_ESCALATION_SCAN, {"tenant_id": seed_tenant["tenant"].id})
    assert "scanned" in out and "escalated_count" in out


# ---------------------------------------------------------------------------
# Staff API
# ---------------------------------------------------------------------------


def _login(client, email: str, password: str = "testpass123") -> dict:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_staff_endpoints_auth_and_flow(db, client, seed_tenant):
    elder = _elder(db, seed_tenant)
    res = IotIngestService.raise_device_sos(db, elder_id=elder.id, mac_address="aa:bb:cc:dd:ee:04")
    incident_id = res["incident_db_id"]

    # No token → rejected (this app answers 403 for a missing bearer).
    assert client.get("/api/v1/care/incidents").status_code in (401, 403)

    # Family portal user → 403.
    family = _family_user(db, elder)
    fam_headers = {"Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'email': family.email, 'password': 'demo1234'}).json()['access_token']}"}
    assert client.get("/api/v1/care/incidents", headers=fam_headers).status_code == 403

    # Viewer can read but not act.
    viewer = _login(client, "viewer@test.example")
    listed = client.get("/api/v1/care/incidents", headers=viewer)
    assert listed.status_code == 200
    row = next(r for r in listed.json() if r["id"] == incident_id)
    assert row["elder_name"] == "Sos Senior"
    assert row["status"] == "open" and row["escalation_level"] == 0 and row["minutes_open"] >= 0
    assert client.post(f"/api/v1/care/incidents/{incident_id}/acknowledge", headers=viewer).status_code == 403

    summary = client.get("/api/v1/care/incidents/summary", headers=viewer).json()
    assert summary["total"] >= 1 and summary["critical"] >= 1

    # Manager acts.
    manager = _login(client, "manager@test.example")
    ack = client.post(f"/api/v1/care/incidents/{incident_id}/acknowledge", headers=manager)
    assert ack.status_code == 200 and ack.json()["status"] == "acknowledged"
    assert ack.json()["acknowledged_by"] == "Test Manager"

    noted = client.post(f"/api/v1/care/incidents/{incident_id}/note", json={"note": "Calling family"}, headers=manager)
    assert noted.status_code == 200
    assert any(e["event"] == "note" and e["detail"] == "Calling family" for e in noted.json()["events"])

    esc = client.post(f"/api/v1/care/incidents/{incident_id}/escalate", json={"reason": "no answer"}, headers=manager)
    assert esc.status_code == 200 and esc.json()["status"] == "escalated" and esc.json()["escalation_level"] == 1

    bad = client.post(f"/api/v1/care/incidents/{incident_id}/resolve", json={"outcome": "other"}, headers=manager)
    assert bad.status_code == 400

    done = client.post(
        f"/api/v1/care/incidents/{incident_id}/resolve",
        json={"outcome": "contacted_family", "note": "Son reached"},
        headers=manager,
    )
    assert done.status_code == 200
    body = done.json()
    assert body["status"] == "resolved" and body["outcome"] == "contacted_family"
    assert body["events"][-1]["event"] == "resolved"

    # Resolved rows drop out of the default list but show with ?status=all.
    assert all(r["id"] != incident_id for r in client.get("/api/v1/care/incidents", headers=manager).json())
    assert any(r["id"] == incident_id for r in client.get("/api/v1/care/incidents?status=all", headers=manager).json())

    detail = client.get(f"/api/v1/care/incidents/{incident_id}", headers=manager)
    assert detail.status_code == 200 and detail.json()["resolution_note"] == "Son reached"


def test_staff_cannot_see_other_tenant(db, client, seed_tenant):
    from app.models.tenant import Tenant

    other = Tenant(name="Other Agency", email="other@test.example", phone="1", address="x", city="y", state="z")
    db.add(other)
    db.flush()
    elder = Elder(tenant_id=other.id, first_name="Far", last_name="Away", status="ACTIVE")
    db.add(elder)
    db.commit()
    row, _ = incident_service.open_incident(db, tenant_id=other.id, elder_id=elder.id, kind="sos_button")
    manager = _login(client, "manager@test.example")
    assert client.get(f"/api/v1/care/incidents/{row.id}", headers=manager).status_code == 404
    assert all(r["id"] != row.id for r in client.get("/api/v1/care/incidents", headers=manager).json())


def test_iot_events_endpoint_reports_duplicate(db, client, seed_tenant, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "IOT_INGEST_API_KEY", "test-ingest-key")
    elder = _elder(db, seed_tenant)
    payload = {
        "event_type": "SOS_BUTTON",
        "elder_id": elder.id,
        "mac_address": "aa:bb:cc:dd:ee:05",
        "dedupe_key": "aa:bb:cc:dd:ee:05:SOS_BUTTON",
    }
    headers = {"X-IoT-Ingest-Key": "test-ingest-key"}
    first = client.post("/api/v1/iot/events", json=payload, headers=headers)
    assert first.status_code == 200 and first.json()["duplicate"] is False
    second = client.post("/api/v1/iot/events", json=payload, headers=headers)
    assert second.status_code == 200 and second.json()["duplicate"] is True
    assert second.json()["incident_id"] == first.json()["incident_id"]


# ---------------------------------------------------------------------------
# Backfill script
# ---------------------------------------------------------------------------


def test_backfill_from_hub_is_idempotent_and_collapses_offline(db, seed_tenant):
    import importlib.util
    from pathlib import Path

    from sqlalchemy.orm.attributes import flag_modified

    spec = importlib.util.spec_from_file_location(
        "backfill_incidents_from_hub",
        Path(__file__).resolve().parents[1] / "scripts" / "backfill_incidents_from_hub.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    elder = _elder(db, seed_tenant, "Legacy", "Hub")
    elder.custom_attributes = {
        "safe_home": {
            "family_hub": {
                "incidents": [
                    {"id": "doff_1", "kind": "device_offline", "status": "open", "created_at": "2026-09-01T10:00:00+00:00", "created_by": "iot:mqtt"},
                    {"id": "doff_2", "kind": "device_offline", "status": "open", "created_at": "2026-09-01T11:00:00+00:00", "created_by": "iot:mqtt"},
                    {"id": "doff_3", "kind": "device_offline", "status": "open", "created_at": "2026-09-01T12:00:00+00:00", "created_by": "iot:mqtt"},
                    {"id": "dsos_1", "kind": "sos", "status": "resolved", "created_at": "2026-09-02T10:00:00+00:00", "created_by": "iot:mqtt", "resolved_at": "2026-09-02T10:30:00+00:00", "resolved_by": "fam@example.com"},
                    {"id": "fsos_1", "kind": "sos", "status": "open", "created_at": "2026-09-03T10:00:00+00:00", "created_by": "fam@example.com"},
                ],
                "alerts": [
                    {"id": "fal_1", "title": "Wearable not heard", "incident_id": "doff_1", "created_at": "2026-09-01T10:00:00+00:00"},
                    {"id": "fal_2", "title": "Wearable not heard", "incident_id": "doff_2", "created_at": "2026-09-01T11:00:00+00:00"},
                    {"id": "fal_3", "title": "Wearable not heard", "incident_id": "doff_3", "created_at": "2026-09-01T12:00:00+00:00"},
                    {"id": "fal_4", "title": "SOS", "incident_id": "fsos_1", "created_at": "2026-09-03T10:00:00+00:00"},
                ],
            }
        }
    }
    flag_modified(elder, "custom_attributes")
    db.commit()

    counts = mod.backfill(db, apply=True)
    assert counts["json_offline_incidents_collapsed"] == 2
    assert counts["json_offline_alerts_collapsed"] == 2
    assert counts["incidents_created"] == 3  # doff_3 (newest), dsos_1, fsos_1

    rows = {r.legacy_id: r for r in db.query(Incident).filter(Incident.elder_id == elder.id).all()}
    assert set(rows) == {"doff_3", "dsos_1", "fsos_1"}
    assert rows["dsos_1"].kind == "sos_button" and rows["dsos_1"].status == "resolved"
    assert rows["fsos_1"].kind == "family_sos" and rows["fsos_1"].status == "open"
    assert rows["doff_3"].kind == "device_offline" and rows["doff_3"].status == "open"

    hub = _hub(db, elder)
    assert [i["id"] for i in hub["incidents"] if i["kind"] == "device_offline"] == ["doff_3"]
    assert {a["id"] for a in hub["alerts"]} == {"fal_3", "fal_4"}

    again = mod.backfill(db, apply=True)
    assert again["incidents_created"] == 0 and again["incidents_skipped_existing"] == 3
    assert db.query(Incident).filter(Incident.elder_id == elder.id).count() == 3
