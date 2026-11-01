"""Phase 4B: client sheet (#94), care plan (#95), risk register + handovers (#98)."""

from datetime import date, datetime, time, timedelta, timezone

from app.core.security import hash_password
from app.livewell import client_care as cc
from app.models.care_job import CareJob
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord
from app.models.user import User

SECRET = "Key safe 4417 behind the tulsi pot"
ATTN = "/api/v1/home-safety/dashboard/attention"


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _user(db, tenant, email, role, **kw):
    u = User(email=email, password_hash=hash_password("testpass123"), first_name=email.split("@")[0],
             last_name="X", role=role, tenant_id=tenant.id, **kw)
    db.add(u)
    db.commit()
    return u


def _family(client, elder):
    ah = _login(client, "admin@test.example")
    r = client.post(f"/api/v1/team/clients/{elder.id}/family-logins", headers=ah,
                    json={"email": "p4b.fam@family.example", "password": "familypass1"})
    assert r.status_code in (200, 201), r.text
    return _login(client, "p4b.fam@family.example", "familypass1")


def _sheet(client, headers, elder_id):
    r = client.put(f"/api/v1/home-safety/clients/{elder_id}/sheet", headers=headers, json={
        "medicines": [{"name": "Metformin", "dose": "500 mg", "times": "Morning, Night"}, {"name": ""}],
        "allergies": "Penicillin",
        "conditions": "Type 2 diabetes",
        "keys_access": SECRET,
        "language": "Telugu",
        "doctor_name": "Dr Rao",
        "doctor_phone": "+91 98480 00000",
        "family_preferences": "Call son before 9 pm",
    })
    assert r.status_code == 200, r.text
    return r.json()


def _job_at(db, seed_tenant, when, caregiver_id=None, status="scheduled"):
    j = CareJob(tenant_id=seed_tenant["tenant"].id, elder_id=seed_tenant["elder"].id,
                caregiver_id=caregiver_id or seed_tenant["caregiver"].id, kind="visit", title="Visit",
                scheduled_at=when, status=status)
    db.add(j)
    db.commit()
    return j


def _noon_ist(days=0):
    d = datetime.now(cc.IST).date() + timedelta(days=days)
    return datetime.combine(d, time(12, 0), tzinfo=cc.IST).astimezone(timezone.utc)


def test_sheet_keys_never_in_family_or_other_team(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    s = _sheet(client, auth_headers, elder.id)
    assert s["keys_access"] == SECRET and s["allergies"] == "Penicillin"
    assert s["medicines"] == [{"name": "Metformin", "dose": "500 mg", "times": "Morning, Night"}]
    assert s["updated_by"]
    assert client.put(f"/api/v1/home-safety/clients/{elder.id}/sheet", headers=auth_headers,
                      json={"doctor_phone": "call me"}).status_code == 400

    # Family: read-only subset, no keys anywhere (care sheet, my details, profile-ish reads).
    fh = _family(client, elder)
    r = client.get("/api/v1/home-safety/family/care-sheet", headers=fh)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "keys_access" not in body["sheet"] and SECRET not in r.text
    assert body["sheet"]["allergies"] == "Penicillin" and body["sheet"]["doctor_name"] == "Dr Rao"
    assert SECRET not in client.get("/api/v1/home-safety/family/my-details", headers=fh).text
    # Family cannot reach the staff routes.
    assert client.get(f"/api/v1/home-safety/clients/{elder.id}/sheet", headers=fh).status_code == 403

    # A manager from another team gets "not found".
    _user(db, seed_tenant["tenant"], "other.mgr@test.example", "CARE_MANAGER")
    oh = _login(client, "other.mgr@test.example")
    for path in ("sheet", "care-plan", "risks", "handovers"):
        r = client.get(f"/api/v1/home-safety/clients/{elder.id}/{path}", headers=oh)
        assert r.status_code == 404 and SECRET not in r.text
    assert client.put(f"/api/v1/home-safety/clients/{elder.id}/sheet", headers=oh,
                      json={"keys_access": "x"}).status_code == 404
    # Audit log keeps field names only.
    from app.models.audit_log import AuditLog

    logs = db.query(AuditLog).filter(AuditLog.entity_type == "client_sheet").all()
    assert logs and all(SECRET not in str(l.new_value) for l in logs)


def test_caregiver_sees_own_client_on_visit_day_only(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    _sheet(client, auth_headers, elder.id)
    cg = seed_tenant["caregiver"]
    _user(db, seed_tenant["tenant"], "p4b.cg@test.example", "CAREGIVER", caregiver_id=cg.id)
    ch = _login(client, "p4b.cg@test.example")

    today = _job_at(db, seed_tenant, _noon_ist())
    r = client.get(f"/api/v1/caregiver-portal/jobs/{today.id}/client-sheet", headers=ch)
    assert r.status_code == 200, r.text
    assert r.json()["keys_access"] == SECRET and r.json()["medicines"][0]["name"] == "Metformin"

    later = _job_at(db, seed_tenant, _noon_ist(days=3))
    assert client.get(f"/api/v1/caregiver-portal/jobs/{later.id}/client-sheet", headers=ch).status_code == 404

    other_cg = Caregiver(tenant_id=cg.tenant_id, first_name="Other", last_name="Cg")
    db.add(other_cg)
    db.commit()
    theirs = _job_at(db, seed_tenant, _noon_ist(), caregiver_id=other_cg.id)
    r = client.get(f"/api/v1/caregiver-portal/jobs/{theirs.id}/client-sheet", headers=ch)
    assert r.status_code == 404 and SECRET not in r.text
    # Staff routes are closed to caregivers.
    assert client.get(f"/api/v1/home-safety/clients/{elder.id}/sheet", headers=ch).status_code == 403


def test_care_plan_review_in_attention_and_family_goals(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    base = f"/api/v1/home-safety/clients/{elder.id}/care-plan"
    g = client.post(f"{base}/goals", headers=auth_headers, json={
        "goal": "Walk to the gate without help", "target_date": "2027-01-31",
        "interventions": ["Walk 10 minutes with support daily", "Grab bar by the door"],
        "progress": "Walking to the kitchen alone now",
    })
    assert g.status_code == 201, g.text
    assert g.json()["status_label"] == "Working on it"

    # Linked to the reassessment: last assessed 178 days ago → reassessment (and review) due in 4 days.
    db.add(HomeSafetyAssessmentRecord(
        assessment_id="p4b-a1", tenant_id=elder.tenant_id, elder_id=elder.id, status="completed", payload={},
        completed_at=datetime.now(timezone.utc) - timedelta(days=178),
    ))
    db.commit()
    plan = client.get(base, headers=auth_headers).json()
    assert plan["review"]["source"] == "reassessment" and plan["review"]["due"] is True
    rows = client.get(ATTN, headers=auth_headers).json()["care_reviews"]
    assert [r["elder_id"] for r in rows] == [elder.id]

    # Reviewed now → next review moves past the heads-up window, so it leaves the dashboard.
    r = client.post(f"{base}/review", headers=auth_headers, json={"reviewed": True})
    assert r.status_code == 200 and r.json()["review"]["source"] == "set"
    assert client.get(ATTN, headers=auth_headers).json()["care_reviews"] == []
    # An explicit overdue date shows as overdue.
    past = (date.today() - timedelta(days=2)).isoformat()
    client.post(f"{base}/review", headers=auth_headers, json={"review_date": past})
    row = client.get(ATTN, headers=auth_headers).json()["care_reviews"][0]
    assert row["overdue"] is True

    # Achieved goals no longer need review; family sees goals in plain words.
    client.put(f"{base}/goals/{g.json()['id']}", headers=auth_headers, json={"status": "achieved"})
    assert client.get(ATTN, headers=auth_headers).json()["care_reviews"] == []
    fam = client.get("/api/v1/home-safety/family/care-sheet", headers=_family(client, elder)).json()
    assert fam["goals"][0]["status_label"] == "Achieved"
    assert fam["goals"][0]["progress"] == "Walking to the kitchen alone now"


def test_risk_register_flags(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    url = f"/api/v1/home-safety/clients/{elder.id}/risks"
    yesterday = (datetime.now(cc.IST).date() - timedelta(days=1)).isoformat()
    later = (datetime.now(cc.IST).date() + timedelta(days=30)).isoformat()
    high = client.post(url, headers=auth_headers, json={"risk": "Falls at night", "level": "high",
                                                        "mitigation": "Night light", "review_date": later}).json()
    client.post(url, headers=auth_headers, json={"risk": "Skips lunch", "level": "low", "review_date": yesterday})
    client.post(url, headers=auth_headers, json={"risk": "Loose rug", "level": "medium", "review_date": later})
    assert client.post(url, headers=auth_headers, json={"risk": "x", "level": "extreme"}).status_code == 400

    flags = client.get(ATTN, headers=auth_headers).json()["risks"]
    assert [(f["risk"], f["review_overdue"]) for f in flags] == [("Falls at night", False), ("Skips lunch", True)]
    assert client.get(ATTN, headers=auth_headers).json()["counts"]["risks"] == 2

    client.put(f"{url}/{high['id']}", headers=auth_headers, json={"status": "closed"})
    assert [f["risk"] for f in client.get(ATTN, headers=auth_headers).json()["risks"]] == ["Skips lunch"]
    listed = client.get(url, headers=auth_headers).json()
    assert listed[-1]["status"] == "closed" and listed[0]["owner_name"]

    # The register is staff-only: not in the family view.
    fam = client.get("/api/v1/home-safety/family/care-sheet", headers=_family(client, elder))
    assert "Skips lunch" not in fam.text and "open_risks" not in fam.json()["sheet"]


def test_handover_client_move_and_acknowledge(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    other = _user(db, seed_tenant["tenant"], "next.mgr@test.example", "CARE_MANAGER")
    oh = _login(client, "next.mgr@test.example")
    # Not in their team yet: no sheet, and they can't hand over a client they don't hold.
    assert client.get(f"/api/v1/home-safety/clients/{elder.id}/sheet", headers=oh).status_code == 404
    bad = client.post("/api/v1/home-safety/handovers", headers=oh, json={
        "kind": "client_move", "to_user_id": seed_tenant["manager"].id, "elder_id": elder.id, "note": "x"})
    assert bad.status_code == 404

    recips = client.get("/api/v1/home-safety/handovers/recipients", headers=auth_headers).json()
    assert other.id in [r["id"] for r in recips]
    r = client.post("/api/v1/home-safety/handovers", headers=auth_headers, json={
        "kind": "client_move", "to_user_id": other.id, "elder_id": elder.id,
        "note": "Daughter prefers WhatsApp; BP meds changed last week"})
    assert r.status_code == 201, r.text
    h = r.json()
    db.refresh(elder)
    assert elder.manager_user_id == other.id

    attn = client.get(ATTN, headers=oh).json()
    assert [x["id"] for x in attn["handovers"]] == [h["id"]]
    # The sender can't acknowledge; the receiver can, once.
    assert client.post(f"/api/v1/home-safety/handovers/{h['id']}/acknowledge", headers=auth_headers).status_code == 404
    ack = client.post(f"/api/v1/home-safety/handovers/{h['id']}/acknowledge", headers=oh)
    assert ack.status_code == 200 and ack.json()["acknowledged_at"]
    assert client.get(ATTN, headers=oh).json()["handovers"] == []
    # Now in their team; the client page lists the handover.
    assert client.get(f"/api/v1/home-safety/clients/{elder.id}/sheet", headers=oh).status_code == 200
    hist = client.get(f"/api/v1/home-safety/clients/{elder.id}/handovers", headers=oh).json()
    assert hist[0]["kind_label"] == "Client moved"
    sent = client.get("/api/v1/home-safety/handovers?box=sent", headers=auth_headers).json()
    assert [x["id"] for x in sent] == [h["id"]]

    # Shift handover without a client; can't hand over to yourself or a caregiver.
    s = client.post("/api/v1/home-safety/handovers", headers=oh, json={
        "to_user_id": seed_tenant["manager"].id, "note": "Two SOS follow-ups pending"})
    assert s.status_code == 201 and s.json()["kind"] == "shift"
    assert client.post("/api/v1/home-safety/handovers", headers=oh, json={
        "to_user_id": other.id, "note": "x"}).status_code == 400


def test_viewer_gets_sheet_without_keys_or_risks(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    _sheet(client, auth_headers, elder.id)
    vh = _login(client, "viewer@test.example")
    r = client.get(f"/api/v1/home-safety/clients/{elder.id}/sheet", headers=vh)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["allergies"] == "Penicillin"
    assert "keys_access" not in body and "open_risks" not in body and SECRET not in r.text
    # Admins and care managers still see them.
    for h in (auth_headers, _login(client, "admin@test.example")):
        assert client.get(f"/api/v1/home-safety/clients/{elder.id}/sheet", headers=h).json()["keys_access"] == SECRET


def test_inactive_caregiver_cannot_open_client_sheet(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    _sheet(client, auth_headers, elder.id)
    cg = seed_tenant["caregiver"]
    _user(db, seed_tenant["tenant"], "p4b.gone@test.example", "CAREGIVER", caregiver_id=cg.id)
    ch = _login(client, "p4b.gone@test.example")
    job = _job_at(db, seed_tenant, _noon_ist())
    assert client.get(f"/api/v1/caregiver-portal/jobs/{job.id}/client-sheet", headers=ch).status_code == 200
    db.get(Caregiver, cg.id).status = "INACTIVE"
    db.commit()
    r = client.get(f"/api/v1/caregiver-portal/jobs/{job.id}/client-sheet", headers=ch)
    assert r.status_code == 404 and SECRET not in r.text
