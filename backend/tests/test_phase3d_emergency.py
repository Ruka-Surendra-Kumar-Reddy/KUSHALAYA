"""Phase 3D — staff-raised emergency, checklist, close, idle escalation, partner link, family view."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.rbac import CAREGIVER, ELDER_PORTAL
from app.core.security import hash_password
from app.livewell import emergency_service, incident_service
from app.models.care_job import CareJob
from app.models.elder import Elder
from app.models.incident import Incident, IncidentEvent, IncidentPartnerLink
from app.models.tenant import Tenant
from app.models.user import User


def _login(client, email: str, password: str = "testpass123") -> dict:
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _elder(db, seed_tenant, *, managed=True, first="Emma", last="Gency") -> Elder:
    elder = Elder(
        tenant_id=seed_tenant["tenant"].id,
        first_name=first,
        last_name=last,
        status="ACTIVE",
        phone="+919000000001",
        address="12 Banjara Hills, Hyderabad",
        emergency_contact_name="Son",
        emergency_contact_phone="+919000000002",
        manager_user_id=seed_tenant["manager"].id if managed else None,
    )
    db.add(elder)
    db.commit()
    db.refresh(elder)
    return elder


def _caregiver_user(db, seed_tenant) -> User:
    user = User(
        email="cg.emergency@example.com",
        password_hash=hash_password("testpass123"),
        first_name="Field",
        last_name="Carer",
        role=CAREGIVER,
        tenant_id=seed_tenant["tenant"].id,
        caregiver_id=seed_tenant["caregiver"].id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _family_user(db, elder: Elder) -> User:
    user = User(
        email=f"family.emg.{elder.id}@example.com",
        password_hash=hash_password("demo1234"),
        first_name="Fam",
        last_name="Ily",
        role=ELDER_PORTAL,
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
        portal_relationship="son",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _raise(client, headers, elder_id, **extra):
    body = {"elder_id": elder_id, "type": "fall", "reported_by": "caregiver", "reporter_phone": "+919000000009",
            "note": "Slipped in bathroom", **extra}
    return client.post("/api/v1/care/incidents/emergency", json=body, headers=headers)


# ---------------------------------------------------------------------------


def test_manager_raises_emergency_in_team_only(db, client, seed_tenant):
    elder = _elder(db, seed_tenant)
    outsider = _elder(db, seed_tenant, managed=False, first="Not", last="Mine")
    manager = _login(client, "manager@test.example")

    res = _raise(client, manager, elder.id)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["kind"] == "staff_emergency" and body["severity"] == "critical"
    assert body["status"] == "acknowledged" and body["owner_name"] == "Test Manager"
    assert body["details"]["type"] == "fall" and body["details"]["reporter_phone"] == "+919000000009"
    assert body["elder_phone"] == "+919000000001" and body["family_phone"] == "+919000000002"
    assert [e["event"] for e in body["events"]][:3] == ["received", "raised", "assigned"]

    # It shows in the normal alerts list.
    listed = client.get("/api/v1/care/incidents", headers=manager).json()
    assert any(r["id"] == body["id"] for r in listed)

    # A second call about the same client joins the open emergency.
    again = _raise(client, manager, elder.id, type="injury")
    assert again.json()["id"] == body["id"]

    # Not in the manager's team → 404; viewer cannot raise.
    assert _raise(client, manager, outsider.id).status_code == 404
    assert _raise(client, _login(client, "viewer@test.example"), elder.id).status_code == 403
    # Admin can raise for anyone in the agency.
    assert _raise(client, _login(client, "admin@test.example"), outsider.id).status_code == 200


def test_caregiver_raises_only_for_own_clients(db, client, seed_tenant):
    mine = _elder(db, seed_tenant)
    other = _elder(db, seed_tenant, first="Other", last="Client")
    db.add(CareJob(tenant_id=mine.tenant_id, elder_id=mine.id, caregiver_id=seed_tenant["caregiver"].id,
                   title="Visit", status="scheduled", scheduled_at=datetime.now(timezone.utc) + timedelta(hours=2)))
    db.commit()
    _caregiver_user(db, seed_tenant)
    cg = _login(client, "cg.emergency@example.com")

    res = client.post("/api/v1/caregiver-portal/emergency",
                      json={"elder_id": mine.id, "type": "chest_breathing", "note": "Short of breath"}, headers=cg)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["created"] is True and out["type_label"] == "Chest pain / breathing"
    # A caregiver's emergency is owned by the client's care manager.
    assert out["owner_name"] == "Test Manager"
    row = db.get(Incident, out["id"])
    assert row.kind == "staff_emergency" and row.owner_user_id == seed_tenant["manager"].id

    assert client.post("/api/v1/caregiver-portal/emergency",
                       json={"elder_id": other.id, "type": "fall"}, headers=cg).status_code == 404
    listed = client.get("/api/v1/caregiver-portal/emergency", headers=cg).json()
    assert [r["id"] for r in listed] == [out["id"]]
    # Caregiver cannot use the staff routes.
    assert _raise(client, cg, mine.id).status_code == 403


def test_step_ticks_record_who_and_when(db, client, seed_tenant):
    elder = _elder(db, seed_tenant)
    manager = _login(client, "manager@test.example")
    inc_id = _raise(client, manager, elder.id).json()["id"]

    url = f"/api/v1/care/incidents/{inc_id}/emergency/step"
    assert client.post(url, json={"step": "call_elder"}, headers=manager).status_code == 200
    assert client.post(url, json={"step": "nonsense"}, headers=manager).status_code == 400
    assert client.post(url, json={"step": "ambulance"}, headers=manager).status_code == 400  # hospital needed
    res = client.post(url, json={"step": "ambulance", "hospital_name": "KIMS"}, headers=manager)
    assert res.status_code == 200
    body = res.json()
    steps = body["details"]["steps"]
    assert set(steps) == {"call_elder", "ambulance"}
    assert steps["call_elder"]["by_name"] == "Test Manager" and steps["call_elder"]["at"]
    assert steps["ambulance"]["hospital_name"] == "KIMS"
    step_events = [e for e in body["events"] if e["event"] == "step"]
    assert len(step_events) == 2 and step_events[-1]["actor_name"] == "Test Manager"
    assert "KIMS" in step_events[-1]["detail"]

    # Owner hand-over to the admin.
    admin_id = seed_tenant["admin"].id
    res = client.post(f"/api/v1/care/incidents/{inc_id}/emergency/owner", json={"user_id": admin_id}, headers=manager)
    assert res.status_code == 200 and res.json()["owner_name"] == "Test Admin"


def test_close_requires_outcome_and_note(db, client, seed_tenant):
    elder = _elder(db, seed_tenant)
    manager = _login(client, "manager@test.example")
    inc_id = _raise(client, manager, elder.id).json()["id"]
    close = f"/api/v1/care/incidents/{inc_id}/emergency/close"

    assert client.post(close, json={"outcome": "resolved_home"}, headers=manager).status_code == 422
    assert client.post(close, json={"outcome": "contacted_family", "note": "x"}, headers=manager).status_code == 400
    # The generic resolve route enforces the same rule for an emergency.
    assert client.post(f"/api/v1/care/incidents/{inc_id}/resolve",
                       json={"outcome": "resolved_home"}, headers=manager).status_code == 400

    res = client.post(close, json={"outcome": "hospital_admission", "note": "Admitted for observation"}, headers=manager)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "resolved" and body["outcome"] == "hospital_admission"
    # Closed: no more steps.
    assert client.post(f"/api/v1/care/incidents/{inc_id}/emergency/step",
                       json={"step": "call_family"}, headers=manager).status_code == 400


def test_idle_escalation_once_per_idle_stretch(db, seed_tenant, monkeypatch):
    elder = _elder(db, seed_tenant)
    sent: list = []
    monkeypatch.setattr(incident_service, "notify_escalation_level",
                        lambda db_, inc_, level, now=None: sent.append(level) or [])
    t0 = datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)
    row, _ = emergency_service.raise_emergency(db, seed_tenant["manager"], elder=elder, emergency_type="fall",
                                               reported_by="elder", now=t0)

    # The normal SOS ladder ignores it (acknowledged on raise); idle < 10 min → nothing.
    assert incident_service.run_escalation_scan(db, now=t0 + timedelta(minutes=9))["escalated_count"] == 0
    out = incident_service.run_escalation_scan(db, now=t0 + timedelta(minutes=11))
    assert out["escalated_count"] == 1 and sent == [1]
    db.refresh(row)
    assert row.status == "escalated" and row.escalation_level == 1

    # Every 2 minutes after that: no repeat while still untouched.
    for m in (13, 15, 30):
        assert incident_service.run_escalation_scan(db, now=t0 + timedelta(minutes=m))["escalated_count"] == 0
    assert sent == [1]

    # A step resets the clock; 10 idle minutes later it escalates again (level 2).
    emergency_service.tick_step(db, row, seed_tenant["manager"], "call_family", now=t0 + timedelta(minutes=31))
    assert incident_service.run_escalation_scan(db, now=t0 + timedelta(minutes=35))["escalated_count"] == 0
    assert incident_service.run_escalation_scan(db, now=t0 + timedelta(minutes=42))["escalated_count"] == 1
    assert sent == [1, 2]


def _setup_partner(db, seed_tenant) -> str:
    tenant = db.get(Tenant, seed_tenant["tenant"].id)
    cfg = emergency_service.save_config(
        db, tenant, {"partners": [{"name": "City Ambulance", "phone": "108", "email": "amb@partner.in", "type": "ambulance"}]}
    )
    return cfg["partners"][0]["id"]


def test_partner_settings_ship_empty_and_admin_only(db, client, seed_tenant):
    admin = _login(client, "admin@test.example")
    manager = _login(client, "manager@test.example")
    got = client.get("/api/v1/care/incidents/emergency/partners", headers=manager).json()
    assert got["partners"] == [] and got["idle_minutes"] == 10
    body = {"partners": [{"name": "Apollo ER", "phone": "040 1066", "email": "er@apollo.in", "type": "hospital"}]}
    assert client.put("/api/v1/care/incidents/emergency/partners", json=body, headers=manager).status_code == 403
    saved = client.put("/api/v1/care/incidents/emergency/partners", json=body, headers=admin).json()
    assert saved["partners"][0]["name"] == "Apollo ER" and saved["partners"][0]["id"]


def test_partner_token_accept_expiry_and_wrong_incident(db, client, seed_tenant, monkeypatch):
    elder = _elder(db, seed_tenant)
    other = _elder(db, seed_tenant, first="Second", last="Person")
    pid = _setup_partner(db, seed_tenant)
    monkeypatch.setattr(incident_service, "deliver_email",
                        lambda rec, **kw: [{"channel": "email", "recipient": rec[0], "ok": True, "detail": "sent"}])
    manager = seed_tenant["manager"]
    row, _ = emergency_service.raise_emergency(db, manager, elder=elder, emergency_type="fall", reported_by="caregiver")
    row2, _ = emergency_service.raise_emergency(db, manager, elder=other, emergency_type="injury", reported_by="family")

    _, link = emergency_service.notify_partner(db, row, manager, pid)
    token = link.rsplit("/", 1)[1]
    assert len(token) >= 40 and f"/emergency-response/{row.id}/" in link
    stored = db.query(IncidentPartnerLink).filter_by(incident_id=row.id).one()
    assert stored.token_hash != token  # only the hash is stored
    db.refresh(row)
    assert "partner_notified" in row.details["steps"]

    base = "/api/v1/home-safety/emergency-response"
    view = client.get(f"{base}/{row.id}/{token}")
    assert view.status_code == 200 and view.json()["client_name"] == "Emma Gency"
    assert view.json()["address"] == "12 Banjara Hills, Hyderabad"

    ok = client.post(f"{base}/{row.id}/{token}", json={"status": "on_the_way", "note": "ETA 12 min"})
    assert ok.status_code == 200 and ok.json()["last_status"] == "on_the_way"
    ev = db.query(IncidentEvent).filter_by(incident_id=row.id, event="partner").order_by(IncidentEvent.id.desc()).first()
    assert ev.detail == "City Ambulance: On the way — ETA 12 min"
    assert client.post(f"{base}/{row.id}/{token}", json={"status": "bogus"}).status_code == 400

    # Token for incident A cannot touch incident B; a made-up token is rejected.
    assert client.get(f"{base}/{row2.id}/{token}").status_code == 404
    assert client.post(f"{base}/{row2.id}/{token}", json={"status": "done"}).status_code == 404
    assert client.get(f"{base}/{row.id}/not-a-real-token").status_code == 404

    # Ops sees the partner's last reply on the detail.
    detail = incident_service.detail_for_tenant(db, elder.tenant_id, row.id)
    assert detail["partners"][0]["last_status"] == "on_the_way"

    # After 48 h: expired, and no client details.
    stored.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    gone = client.get(f"{base}/{row.id}/{token}").json()
    assert gone["expired"] is True and gone["client_name"] is None and gone["address"] is None
    assert client.post(f"{base}/{row.id}/{token}", json={"status": "done"}).status_code == 410


def test_family_sees_plain_status_only(db, client, seed_tenant):
    elder = _elder(db, seed_tenant)
    family = _family_user(db, elder)
    fam = {"Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'email': family.email, 'password': 'demo1234'}).json()['access_token']}"}
    manager = _login(client, "manager@test.example")
    inc_id = _raise(client, manager, elder.id, note="Bleeding from head, reporter is neighbour").json()["id"]
    # Care team first (29 Oct): nothing for the family until staff tap "Notify family".
    assert client.get("/api/v1/home-safety/family/incidents", headers=fam).json() == []
    assert client.post(f"/api/v1/sos-siren/incidents/{inc_id}/notify-family", headers=manager, json={}).status_code == 200

    rows = client.get("/api/v1/home-safety/family/incidents", headers=fam)
    assert rows.status_code == 200, rows.text
    mine = [r for r in rows.json() if r["kind"] == "emergency"]
    assert len(mine) == 1
    assert mine[0]["status"] == "open" and mine[0]["note"] == "Emergency — our team is handling it"
    text = str(rows.json())
    assert "Bleeding" not in text and "+919000000009" not in text

    # Family cannot close a staff emergency.
    legacy = mine[0]["id"]
    assert client.post(f"/api/v1/home-safety/family/incidents/{legacy}/resolve", headers=fam).status_code == 400

    client.post(f"/api/v1/care/incidents/{inc_id}/emergency/step",
                json={"step": "ambulance", "hospital_name": "KIMS"}, headers=manager)
    client.post(f"/api/v1/care/incidents/{inc_id}/emergency/close",
                json={"outcome": "hospital_admission", "note": "Head wound, CT normal"}, headers=manager)
    after = [r for r in client.get("/api/v1/home-safety/family/incidents", headers=fam).json() if r["kind"] == "emergency"][0]
    assert after["status"] == "resolved"
    assert after["note"] == "Emergency closed — admitted to hospital (KIMS)"
    assert "CT normal" not in str(after)


# --- Phase 3 fixes -----------------------------------------------------------


def test_caregiver_scope_is_current_jobs_and_job_id_checked(db, client, seed_tenant):
    cg_id = seed_tenant["caregiver"].id
    now = datetime.now(timezone.utc)
    current = _elder(db, seed_tenant, first="Now", last="Client")
    old = _elder(db, seed_tenant, first="Old", last="Client")
    dropped = _elder(db, seed_tenant, first="Dropped", last="Client")
    job = CareJob(tenant_id=current.tenant_id, elder_id=current.id, caregiver_id=cg_id,
                  title="Visit", status="scheduled", scheduled_at=now + timedelta(hours=3))
    db.add_all([
        job,
        CareJob(tenant_id=old.tenant_id, elder_id=old.id, caregiver_id=cg_id,
                title="Visit", status="completed", scheduled_at=now - timedelta(days=10)),
        CareJob(tenant_id=dropped.tenant_id, elder_id=dropped.id, caregiver_id=cg_id,
                title="Visit", status="cancelled", scheduled_at=now + timedelta(hours=1)),
    ])
    other_job = CareJob(tenant_id=old.tenant_id, elder_id=old.id, caregiver_id=cg_id,
                        title="Visit", status="completed", scheduled_at=now - timedelta(days=12))
    db.add(other_job)
    db.commit()
    ids = emergency_service.caregiver_elder_ids(db, cg_id)
    assert current.id in ids and old.id not in ids and dropped.id not in ids

    _caregiver_user(db, seed_tenant)
    cg = _login(client, "cg.emergency@example.com")
    url = "/api/v1/caregiver-portal/emergency"
    assert client.post(url, json={"elder_id": old.id, "type": "fall"}, headers=cg).status_code == 404
    assert client.post(url, json={"elder_id": dropped.id, "type": "fall"}, headers=cg).status_code == 404
    # A job id for another client is ignored, not stored.
    res = client.post(url, json={"elder_id": current.id, "type": "fall", "job_id": other_job.id}, headers=cg)
    assert res.status_code == 200, res.text
    row = db.get(Incident, res.json()["id"])
    db.refresh(row)
    assert row.details["job_id"] is None


def test_caregiver_job_id_kept_when_own(db, client, seed_tenant):
    elder = _elder(db, seed_tenant)
    job = CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, caregiver_id=seed_tenant["caregiver"].id,
                  title="Visit", status="checked_in", scheduled_at=datetime.now(timezone.utc))
    db.add(job)
    db.commit()
    _caregiver_user(db, seed_tenant)
    cg = _login(client, "cg.emergency@example.com")
    res = client.post("/api/v1/caregiver-portal/emergency",
                      json={"elder_id": elder.id, "type": "fall", "job_id": job.id}, headers=cg)
    assert res.status_code == 200, res.text
    row = db.get(Incident, res.json()["id"])
    db.refresh(row)
    assert row.details["job_id"] == job.id


def test_closed_emergency_hides_client_from_partner_and_expires_links(db, client, seed_tenant, monkeypatch):
    elder = _elder(db, seed_tenant)
    pid = _setup_partner(db, seed_tenant)
    monkeypatch.setattr(incident_service, "deliver_email",
                        lambda rec, **kw: [{"channel": "email", "recipient": rec[0], "ok": True, "detail": "sent"}])
    manager = seed_tenant["manager"]
    row, _ = emergency_service.raise_emergency(db, manager, elder=elder, emergency_type="fall", reported_by="caregiver")
    _, link = emergency_service.notify_partner(db, row, manager, pid)
    token = link.rsplit("/", 1)[1]
    base = f"/api/v1/home-safety/emergency-response/{row.id}/{token}"
    assert client.get(base).json()["client_name"] == "Emma Gency"

    emergency_service.close(db, row, manager, outcome="resolved_home", note="All fine")
    view = client.get(base).json()
    assert view["closed"] is True and view["expired"] is True
    assert view["client_name"] is None and view["address"] is None and view["client_phone"] is None
    stored = db.query(IncidentPartnerLink).filter_by(incident_id=row.id).one()
    db.refresh(stored)
    assert incident_service._aware(stored.expires_at) <= datetime.now(timezone.utc)


def test_generic_resolve_rejects_emergency(db, client, seed_tenant):
    elder = _elder(db, seed_tenant)
    manager = _login(client, "manager@test.example")
    inc_id = _raise(client, manager, elder.id).json()["id"]
    res = client.post(f"/api/v1/care/incidents/{inc_id}/resolve",
                      json={"outcome": "resolved_home", "note": "Private staff note"}, headers=manager)
    assert res.status_code == 400 and "Close emergency" in res.json()["detail"]
    assert db.get(Incident, inc_id).status in ("open", "acknowledged")


def test_raise_twice_joins_one(db, seed_tenant):
    elder = _elder(db, seed_tenant)
    manager = seed_tenant["manager"]
    a, created_a = emergency_service.raise_emergency(db, manager, elder=elder, emergency_type="fall", reported_by="caregiver")
    b, created_b = emergency_service.raise_emergency(db, manager, elder=elder, emergency_type="injury", reported_by="family")
    assert created_a and not created_b and a.id == b.id


def test_partner_page_always_shows_care_team_phone(db, client, seed_tenant, monkeypatch):
    from app.livewell.care_team_contact import DEFAULT_PHONE

    elder = _elder(db, seed_tenant)
    pid = _setup_partner(db, seed_tenant)
    monkeypatch.setattr(incident_service, "deliver_email",
                        lambda rec, **kw: [{"channel": "email", "recipient": rec[0], "ok": True, "detail": "sent"}])
    manager = seed_tenant["manager"]
    row, _ = emergency_service.raise_emergency(db, manager, elder=elder, emergency_type="fall", reported_by="caregiver")
    _, link = emergency_service.notify_partner(db, row, manager, pid)
    token = link.rsplit("/", 1)[1]
    base = "/api/v1/home-safety/emergency-response"
    ok = client.get(f"{base}/{row.id}/{token}").json()
    assert ok["care_team_phone"] and ok["care_team_tel"].startswith("+")
    emergency_service.close(db, row, manager, outcome="resolved_home", note="Fine")
    assert client.get(f"{base}/{row.id}/{token}").json()["care_team_phone"]
    bad = client.get(f"{base}/{row.id}/not-a-real-token")
    assert bad.status_code == 404 and bad.json()["detail"] == "This link is not valid"
    assert bad.json()["care_team_phone"] == DEFAULT_PHONE
