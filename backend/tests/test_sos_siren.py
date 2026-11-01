"""C1 SOS siren: recipients, care team first then "Notify family", false alarm, acknowledge, escalation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.rbac import CAREGIVER, ELDER_PORTAL
from app.core.security import hash_password
from app.livewell import emergency_service, incident_service, sos_siren
from app.livewell.family_care_hub import FamilyCareHubService
from app.livewell.iot_ingest_service import IotIngestService
from app.models.elder import Elder
from app.models.incident import Incident
from app.models.sos_siren import SosSirenAlert
from app.models.user import User


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


def _world(db, seed_tenant):
    elder = seed_tenant["elder"]
    other_elder = Elder(tenant_id=seed_tenant["tenant"].id, first_name="Other", last_name="Client", status="ACTIVE")
    db.add(other_elder)
    db.commit()
    return {
        "elder": elder,
        "son": _user(db, seed_tenant, "son@sos.example", ELDER_PORTAL, elder_id=elder.id, portal_relationship="son"),
        "daughter": _user(db, seed_tenant, "daughter@sos.example", ELDER_PORTAL, elder_id=elder.id,
                          portal_relationship="daughter"),
        "self": _user(db, seed_tenant, "elder.self@sos.example", ELDER_PORTAL, elder_id=elder.id,
                      portal_relationship="self"),
        "stranger": _user(db, seed_tenant, "stranger@sos.example", ELDER_PORTAL, elder_id=other_elder.id,
                          portal_relationship="son"),
        "other_manager": _user(db, seed_tenant, "othermgr@sos.example", "CARE_MANAGER"),
    }


def _rows(db, incident_id) -> dict[int, SosSirenAlert]:
    return {r.user_id: r for r in db.query(SosSirenAlert).filter(SosSirenAlert.incident_id == incident_id).all()}


def _hub_sos(db, elder) -> list[dict]:
    db.refresh(elder)
    hub = (elder.custom_attributes or {}).get("safe_home", {}).get("family_hub", {})
    return [i for i in hub.get("incidents") or [] if isinstance(i, dict) and i.get("kind") == "sos"]


def _family_alerts(db, user) -> list[dict]:
    return FamilyCareHubService.list_alerts(db, user, include_info=True)


def test_family_sos_goes_to_care_team_first_then_family_on_notify(db, client, seed_tenant):
    w = _world(db, seed_tenant)
    sos = FamilyCareHubService.raise_sos(db, w["son"], "Help")
    row = incident_service.find_by_legacy_id(db, w["elder"].id, sos["id"])
    rows = _rows(db, row.id)

    admin, manager = seed_tenant["admin"], seed_tenant["manager"]
    # Care team + the presser only: the rest of the family is not alerted yet.
    assert set(rows) == {admin.id, manager.id, w["son"].id}
    for outsider in (w["other_manager"], w["stranger"], seed_tenant["viewer"], w["daughter"], w["self"]):
        assert outsider.id not in rows
    assert sos_siren.active_for(db, w["daughter"]) == []
    # Nothing in the other family logins' portal either; the presser sees their SOS.
    assert FamilyCareHubService.list_incidents(db, w["daughter"]) == []
    assert _family_alerts(db, w["daughter"]) == []
    assert [i["id"] for i in FamilyCareHubService.list_incidents(db, w["son"])] == [sos["id"]]
    # Per device (27 Oct): the presser's other devices show it; the pressing device stays quiet locally.
    mine = sos_siren.active_for(db, w["son"])
    assert len(mine) == 1 and mine[0]["pressed_by_me"] is True and mine[0]["audience"] == "family"

    # Acknowledging tells the presser only.
    incident_service.acknowledge(db, row, manager)
    assert _family_alerts(db, w["daughter"]) == []
    assert any("seen the alert" in a["title"] for a in _family_alerts(db, w["son"]))

    mgr = _login(client, "manager@test.example")
    # Notify family before confirming is refused.
    r = client.post(f"/api/v1/sos-siren/incidents/{row.id}/notify-family", headers=mgr, json={})
    assert r.status_code == 400
    # A family login cannot notify.
    fam = _login(client, "son@sos.example")
    assert client.post(f"/api/v1/sos-siren/incidents/{row.id}/notify-family", headers=fam, json={}).status_code == 403

    assert client.post(f"/api/v1/sos-siren/incidents/{row.id}/confirm", headers=mgr).status_code == 200
    db.refresh(row)
    assert sos_siren.family_held(row)  # confirming alone does not tell the family
    steps = client.get(f"/api/v1/care/incidents/{row.id}", headers=mgr).json()["sos"]
    assert steps["family_held"] is True and steps["can_notify_family"] is True and steps["can_confirm"] is False
    assert sos_siren.active_for(db, w["daughter"]) == []
    card = sos_siren.active_for(db, admin)  # the manager acked above; the admin's card is still up
    assert card and card[0]["notify_family"] is True and card[0]["verify"] is False

    r = client.post(
        f"/api/v1/sos-siren/incidents/{row.id}/notify-family", headers=mgr, json={"message": "Ambulance on the way"},
    )
    assert r.status_code == 200, r.text
    rows = _rows(db, row.id)
    # Every family login of this client (the client's own login too), nobody else.
    assert set(rows) == {admin.id, manager.id, w["son"].id, w["daughter"].id, w["self"].id}
    assert rows[w["daughter"].id].audience == "family"
    assert sos_siren.active_for(db, w["stranger"]) == []
    assert sos_siren.active_for(db, manager) == []  # the notifier's card is done
    daughter = sos_siren.active_for(db, w["daughter"])
    assert len(daughter) == 1 and daughter[0]["pressed_by"].startswith("Son") and daughter[0]["pressed_by_me"] is False
    assert [i["id"] for i in FamilyCareHubService.list_incidents(db, w["daughter"])] == [sos["id"]]
    alerts = _family_alerts(db, w["daughter"])
    assert any("Ambulance on the way" in a["body"] for a in alerts)
    assert _family_alerts(db, w["stranger"]) == []
    # Twice is harmless.
    assert client.post(f"/api/v1/sos-siren/incidents/{row.id}/notify-family", headers=mgr, json={}).status_code == 200


def test_elder_login_sos_is_labelled_as_the_client(db, seed_tenant):
    w = _world(db, seed_tenant)
    sos = FamilyCareHubService.raise_sos(db, w["self"], None)
    row = incident_service.find_by_legacy_id(db, w["elder"].id, sos["id"])
    item = sos_siren.active_for(db, seed_tenant["manager"])[0]
    assert item["incident_id"] == row.id and item["pressed_by"].endswith("(the client)")
    assert not {w["son"].id, w["daughter"].id} & set(_rows(db, row.id))


def test_caregiver_emergency_sounds_siren(db, seed_tenant):
    w = _world(db, seed_tenant)
    cg = _user(db, seed_tenant, "cg@sos.example", CAREGIVER, caregiver_id=seed_tenant["caregiver"].id)
    row, created = emergency_service.raise_emergency(
        db, cg, elder=w["elder"], emergency_type="fall", reported_by="caregiver",
    )
    assert created
    rows = _rows(db, row.id)
    assert cg.id not in rows
    assert set(rows) == {seed_tenant["admin"].id, seed_tenant["manager"].id}  # family not yet
    item = sos_siren.active_for(db, seed_tenant["manager"])[0]
    assert item["title"] == "Emergency" and item["verify"] is True  # a caregiver's raise needs confirming
    assert FamilyCareHubService.list_incidents(db, w["son"]) == []


def test_manager_emergency_is_confirmed_but_family_waits_for_notify(db, client, seed_tenant):
    w = _world(db, seed_tenant)
    row, created = emergency_service.raise_emergency(
        db, seed_tenant["manager"], elder=w["elder"], emergency_type="fall", reported_by="caregiver",
    )
    assert created and sos_siren.siren(row)["confirmed_at"] and sos_siren.family_held(row)
    assert FamilyCareHubService.list_incidents(db, w["son"]) == [] and _family_alerts(db, w["son"]) == []
    adm = _login(client, "admin@test.example")
    r = client.post(f"/api/v1/sos-siren/incidents/{row.id}/notify-family", headers=adm, json={})
    assert r.status_code == 200, r.text
    assert [i["kind"] for i in FamilyCareHubService.list_incidents(db, w["son"])] == ["emergency"]
    assert {w["son"].id, w["daughter"].id, w["self"].id} <= set(_rows(db, row.id))


def test_watch_sos_goes_to_staff_first_then_family_on_notify(db, client, seed_tenant):
    w = _world(db, seed_tenant)
    res = IotIngestService.raise_device_sos(db, elder_id=w["elder"].id, mac_address="aa:bb:cc:dd:ee:10")
    row = db.get(Incident, res["incident_db_id"])
    rows = _rows(db, row.id)
    assert set(rows) == {seed_tenant["admin"].id, seed_tenant["manager"].id}
    assert _hub_sos(db, w["elder"]) == []  # family hears nothing yet
    item = sos_siren.active_for(db, seed_tenant["manager"])[0]
    assert item["title"] == "Watch SOS — verify" and item["verify"] is True

    # Acknowledging does not tell the family either.
    incident_service.acknowledge(db, row, seed_tenant["admin"])
    assert _hub_sos(db, w["elder"]) == []

    # A family login cannot confirm.
    fam = _login(client, "son@sos.example")
    assert client.post(f"/api/v1/sos-siren/incidents/{row.id}/confirm", headers=fam).status_code == 403

    mgr = _login(client, "manager@test.example")
    r = client.post(f"/api/v1/sos-siren/incidents/{row.id}/confirm", headers=mgr)
    assert r.status_code == 200, r.text
    assert _hub_sos(db, w["elder"]) == []  # confirmed, still not told
    r = client.post(f"/api/v1/sos-siren/incidents/{row.id}/notify-family", headers=mgr, json={})
    assert r.status_code == 200, r.text
    rows = _rows(db, row.id)
    assert {w["son"].id, w["daughter"].id} <= set(rows)
    assert w["stranger"].id not in rows and w["other_manager"].id not in rows
    assert len(_hub_sos(db, w["elder"])) == 1
    fam_item = client.get("/api/v1/sos-siren/active", headers=fam).json()
    assert len(fam_item) == 1 and fam_item[0]["verify"] is False and fam_item[0]["call"]["label"]


def test_watch_false_alarm_never_reaches_family(db, client, seed_tenant):
    w = _world(db, seed_tenant)
    res = IotIngestService.raise_device_sos(db, elder_id=w["elder"].id, mac_address="aa:bb:cc:dd:ee:11")
    mgr = _login(client, "manager@test.example")
    r = client.post(f"/api/v1/sos-siren/incidents/{res['incident_db_id']}/false-alarm", headers=mgr, json={})
    assert r.status_code == 200, r.text
    row = db.get(Incident, res["incident_db_id"])
    db.refresh(row)
    assert row.status == "resolved" and row.outcome == "false_alarm"
    assert all(r.audience == "staff" for r in _rows(db, row.id).values())
    assert _hub_sos(db, w["elder"]) == []
    assert sos_siren.active_for(db, seed_tenant["admin"]) == []
    assert _family_alerts(db, w["son"]) == []
    # Confirm after close is refused.
    assert client.post(f"/api/v1/sos-siren/incidents/{row.id}/confirm", headers=mgr).status_code == 400


def test_family_sos_false_alarm_tells_only_the_presser(db, client, seed_tenant):
    w = _world(db, seed_tenant)
    sos = FamilyCareHubService.raise_sos(db, w["son"], "Pressed by mistake?")
    row = incident_service.find_by_legacy_id(db, w["elder"].id, sos["id"])
    mgr = _login(client, "manager@test.example")
    r = client.post(f"/api/v1/sos-siren/incidents/{row.id}/false-alarm", headers=mgr, json={})
    assert r.status_code == 200, r.text
    db.refresh(row)
    assert row.status == "resolved" and row.outcome == "false_alarm"
    assert all(r.audience == "staff" or r.user_id == w["son"].id for r in _rows(db, row.id).values())
    # The presser sees it was handled; nobody else in the family hears anything.
    mine = FamilyCareHubService.list_incidents(db, w["son"])
    assert mine[0]["status"] == "resolved"
    assert any(a["title"] == "SOS checked — all clear" for a in _family_alerts(db, w["son"]))
    for other in (w["daughter"], w["self"]):
        assert FamilyCareHubService.list_incidents(db, other) == [] and _family_alerts(db, other) == []
    assert sos_siren.active_for(db, w["son"]) == []
    # Notify after close is refused.
    assert client.post(f"/api/v1/sos-siren/incidents/{row.id}/notify-family", headers=mgr, json={}).status_code == 400


def test_closing_a_held_sos_tells_only_the_presser(db, seed_tenant):
    w = _world(db, seed_tenant)
    sos = FamilyCareHubService.raise_sos(db, w["son"], "Help")
    row = incident_service.find_by_legacy_id(db, w["elder"].id, sos["id"])
    incident_service.resolve(db, row, outcome="contacted_family", note="Called him", user=seed_tenant["manager"])
    assert any(a["title"] == "Alert closed" for a in _family_alerts(db, w["son"]))
    assert _family_alerts(db, w["daughter"]) == []


def test_manager_outside_team_cannot_confirm(db, client, seed_tenant):
    w = _world(db, seed_tenant)
    res = IotIngestService.raise_device_sos(db, elder_id=w["elder"].id, mac_address="aa:bb:cc:dd:ee:12")
    other = _login(client, "othermgr@sos.example")
    assert client.post(f"/api/v1/sos-siren/incidents/{res['incident_db_id']}/confirm", headers=other).status_code == 404


def test_acknowledge_stops_it_for_that_person_and_shows_to_others(db, client, seed_tenant):
    w = _world(db, seed_tenant)
    FamilyCareHubService.raise_sos(db, w["son"], "Help")
    mgr = _login(client, "manager@test.example")
    items = client.get("/api/v1/sos-siren/active", headers=mgr).json()
    assert len(items) == 1
    r = client.post(f"/api/v1/sos-siren/{items[0]['id']}/acknowledge", headers=mgr)
    assert r.status_code == 200, r.text
    assert client.get("/api/v1/sos-siren/active", headers=mgr).json() == []

    row = db.get(Incident, items[0]["incident_id"])
    db.refresh(row)
    assert row.acknowledged_by_user_id == seed_tenant["manager"].id  # staff ack acknowledges the incident
    admin_item = sos_siren.active_for(db, seed_tenant["admin"])[0]
    assert admin_item["acknowledged_by"] and admin_item["acknowledged_by"][0].startswith("Test Manager")

    # Someone else's alert row cannot be acknowledged.
    admin_row = _rows(db, row.id)[seed_tenant["admin"].id]
    assert client.post(f"/api/v1/sos-siren/{admin_row.id}/acknowledge", headers=mgr).status_code == 404


def test_escalates_to_heads_after_two_minutes_without_staff_ack(db, seed_tenant):
    w = _world(db, seed_tenant)
    sos = FamilyCareHubService.raise_sos(db, w["son"], "Help")
    row = incident_service.find_by_legacy_id(db, w["elder"].id, sos["id"])
    pressed = datetime.fromisoformat(sos_siren.siren(row)["pressed_at"])

    assert sos_siren.run_escalation(db, now=pressed + timedelta(seconds=90)) == []
    out = sos_siren.run_escalation(db, now=pressed + timedelta(minutes=3))
    assert [o["incident_id"] for o in out] == [row.id]
    db.refresh(row)
    assert row.status == "escalated" and sos_siren.siren(row)["escalated_at"]
    assert sos_siren.active_for(db, seed_tenant["admin"])[0]["escalated"] is True
    # Once only.
    assert sos_siren.run_escalation(db, now=pressed + timedelta(minutes=6)) == []


def test_staff_presser_rings_on_their_other_devices_but_does_not_escalate(db, seed_tenant):
    """Per device (27 Oct): the presser's account is not silenced, but a staff
    member who raised it is already handling it, so it does not escalate."""
    w = _world(db, seed_tenant)
    manager = seed_tenant["manager"]
    row, created = emergency_service.raise_emergency(
        db, manager, elder=w["elder"], emergency_type="fall", reported_by="caregiver",
    )
    assert created
    mine = sos_siren.active_for(db, manager)
    assert len(mine) == 1 and mine[0]["pressed_by_me"] is True
    pressed = datetime.fromisoformat(sos_siren.siren(row)["pressed_at"])
    assert sos_siren.run_escalation(db, now=pressed + timedelta(minutes=5)) == []


def test_no_escalation_once_staff_acknowledged(db, seed_tenant):
    w = _world(db, seed_tenant)
    sos = FamilyCareHubService.raise_sos(db, w["son"], "Help")
    row = incident_service.find_by_legacy_id(db, w["elder"].id, sos["id"])
    mine = _rows(db, row.id)[seed_tenant["manager"].id]
    sos_siren.acknowledge(db, mine.id, seed_tenant["manager"])
    later = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert sos_siren.run_escalation(db, now=later) == []


def test_family_ack_does_not_count_as_staff_ack(db, seed_tenant):
    w = _world(db, seed_tenant)
    sos = FamilyCareHubService.raise_sos(db, w["son"], "Help")
    row = incident_service.find_by_legacy_id(db, w["elder"].id, sos["id"])
    sos_siren.acknowledge(db, _rows(db, row.id)[w["son"].id].id, w["son"])
    db.refresh(row)
    assert row.acknowledged_at is None
    later = datetime.now(timezone.utc) + timedelta(minutes=3)
    assert [o["incident_id"] for o in sos_siren.run_escalation(db, now=later)] == [row.id]
