"""Phase 1D Clients: edit details, family login status, Assessments tab, list badges."""

from datetime import datetime, timedelta, timezone

from app.models.care_job import CareJob
from app.models.elder import Elder
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _mine_and_outside(db, seed_tenant):
    elder = seed_tenant["elder"]
    elder.manager_user_id = seed_tenant["manager"].id
    outside = Elder(tenant_id=seed_tenant["tenant"].id, first_name="Out", last_name="Side", care_level="Low", status="ACTIVE")
    db.add(outside)
    db.commit()
    return elder, outside


def test_edit_details_is_team_scoped(client, db, seed_tenant):
    elder, outside = _mine_and_outside(db, seed_tenant)
    mgr = _login(client, "manager@test.example")
    body = {"phone": "+91 90000 11111", "allergies": "Penicillin", "mobility_status": "Walker", "emergency_contact_name": "Ravi"}
    res = client.put(f"/api/v1/elders/{elder.id}", json=body, headers=mgr)
    assert res.status_code == 200, res.text
    prof = client.get(f"/api/v1/home-safety/clients/{elder.id}/profile", headers=mgr).json()["person"]
    assert prof["allergies"] == "Penicillin" and prof["mobility_status"] == "Walker"
    assert client.put(f"/api/v1/elders/{outside.id}", json=body, headers=mgr).status_code == 404


def test_family_login_deactivate_and_reactivate(client, db, seed_tenant):
    elder, outside = _mine_and_outside(db, seed_tenant)
    admin = _login(client, "admin@test.example")
    for e, email in ((elder, "fam.a@family.example"), (outside, "fam.b@family.example")):
        r = client.post(f"/api/v1/team/clients/{e.id}/family-logins", headers=admin,
                        json={"email": email, "password": "familypass1", "name": "Ravi Rao", "relationship": "son"})
        assert r.status_code == 201, r.text
    mgr = _login(client, "manager@test.example")
    logins = client.get(f"/api/v1/team/clients/{elder.id}/family-logins", headers=mgr).json()
    assert [f["email"] for f in logins] == ["fam.a@family.example"] and logins[0]["active"]
    uid = logins[0]["id"]

    base = f"/api/v1/team/clients/{elder.id}/family-logins/{uid}"
    off = client.put(f"{base}/status", json={"active": False}, headers=mgr)
    assert off.status_code == 200 and off.json()["active"] is False
    assert client.post("/api/v1/auth/login", json={"email": "fam.a@family.example", "password": "familypass1"}).status_code != 200
    on = client.put(f"{base}/status", json={"active": True}, headers=mgr)
    assert on.json()["active"] is True
    _login(client, "fam.a@family.example", "familypass1")

    # Outside the manager's team: not found, for listing and status alike.
    assert client.get(f"/api/v1/team/clients/{outside.id}/family-logins", headers=mgr).status_code == 404
    other_id = client.get(f"/api/v1/team/clients/{outside.id}/family-logins", headers=admin).json()[0]["id"]
    assert client.put(f"/api/v1/team/clients/{outside.id}/family-logins/{other_id}/status",
                      json={"active": False}, headers=mgr).status_code == 404
    # The outside login through the manager's own client id: not linked there, so not found.
    assert client.put(f"/api/v1/team/clients/{elder.id}/family-logins/{other_id}/password",
                      json={"password": "newpass123"}, headers=mgr).status_code == 404
    # The old id-only password route is admin-only now.
    assert client.put(f"/api/v1/team/family-logins/{uid}/password", json={"password": "newpass123"}, headers=mgr).status_code == 403


def test_family_logins_follow_links_and_shared_login_needs_admin(client, db, seed_tenant):
    """A login linked to two clients shows on both; a manager who sees only one cannot deactivate it."""
    from app.models.family_elder_link import FamilyElderLink
    from app.models.user import User

    elder, outside = _mine_and_outside(db, seed_tenant)
    admin = _login(client, "admin@test.example")
    client.post(f"/api/v1/team/clients/{outside.id}/family-logins", headers=admin,
                json={"email": "shared@family.example", "password": "familypass1"})
    u = db.query(User).filter(User.email == "shared@family.example").first()
    db.add(FamilyElderLink(user_id=u.id, elder_id=elder.id))  # users.elder_id stays on the other client
    db.commit()
    mgr = _login(client, "manager@test.example")
    listed = client.get(f"/api/v1/team/clients/{elder.id}/family-logins", headers=mgr).json()
    assert [f["email"] for f in listed] == ["shared@family.example"]
    base = f"/api/v1/team/clients/{elder.id}/family-logins/{u.id}"
    assert client.put(f"{base}/password", json={"password": "newpass123"}, headers=mgr).status_code == 200
    assert client.put(f"{base}/status", json={"active": False}, headers=mgr).status_code == 400
    assert client.put(f"{base}/status", json={"active": False}, headers=admin).json()["active"] is False


def test_manager_cannot_change_status_or_score_block(client, db, seed_tenant):
    elder, _outside = _mine_and_outside(db, seed_tenant)
    elder.custom_attributes = {"safe_home": {"safety_score": {"total": 71}}}
    db.commit()
    mgr = _login(client, "manager@test.example")
    res = client.put(f"/api/v1/elders/{elder.id}", headers=mgr, json={
        "status": "INACTIVE", "phone": "+91 1",
        "custom_attributes": {"safe_home": {"safety_score": {"total": 99}}, "notes_extra": "ok"},
    })
    assert res.status_code == 200, res.text
    db.expire_all()
    e = db.get(Elder, elder.id)
    assert e.status == "ACTIVE" and e.phone == "+91 1"
    assert e.custom_attributes["safe_home"]["safety_score"]["total"] == 71
    assert e.custom_attributes.get("notes_extra") == "ok"
    admin = _login(client, "admin@test.example")
    assert client.put(f"/api/v1/elders/{elder.id}", headers=admin, json={"status": "PAUSED"}).status_code == 200
    db.expire_all()
    assert db.get(Elder, elder.id).status == "PAUSED"


def test_assessments_tab_lists_records_and_booked_job(client, db, seed_tenant):
    elder, outside = _mine_and_outside(db, seed_tenant)
    tid = seed_tenant["tenant"].id
    now = datetime.now(timezone.utc)
    db.add_all([
        HomeSafetyAssessmentRecord(assessment_id="a-old", tenant_id=tid, elder_id=elder.id, status="completed",
                                   payload={"independenceScore": 60, "assessorName": "Priya"}, server_score=60,
                                   completed_at=now - timedelta(days=200)),
        HomeSafetyAssessmentRecord(assessment_id="a-new", tenant_id=tid, elder_id=elder.id, status="completed",
                                   payload={"independenceScore": 68}, server_score=68, completed_at=now - timedelta(days=5)),
        HomeSafetyAssessmentRecord(assessment_id="a-draft", tenant_id=tid, elder_id=elder.id, status="draft", payload={}),
    ])
    db.add(CareJob(tenant_id=tid, elder_id=elder.id, kind="assessment", title="Reassessment",
                   scheduled_at=now + timedelta(days=2), status="scheduled"))
    db.commit()
    mgr = _login(client, "manager@test.example")
    res = client.get(f"/api/v1/home-safety/clients/{elder.id}/assessments", headers=mgr)
    assert res.status_code == 200, res.text
    data = res.json()
    by_id = {a["id"]: a for a in data["assessments"]}
    assert by_id["a-new"]["score"] == 68 and by_id["a-new"]["change"] == 8
    assert by_id["a-new"]["band"]
    assert by_id["a-old"]["assessor"] == "Priya"
    assert by_id["a-draft"]["status"] == "in_progress" and by_id["a-draft"]["status_label"] == "In progress" and by_id["a-draft"]["score"] is None
    assert len(data["booked"]) == 1 and data["booked"][0]["started"] is False
    assert data["compare"]["now"]["score"] == 68 and data["compare"]["before"]["score"] == 60
    assert client.get(f"/api/v1/home-safety/clients/{outside.id}/assessments", headers=mgr).status_code == 404


def test_client_list_badges(client, db, seed_tenant):
    elder, _outside = _mine_and_outside(db, seed_tenant)
    db.add(CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, kind="visit", title="Visit",
                   scheduled_at=datetime.now(timezone.utc) + timedelta(days=3), status="scheduled"))
    db.commit()
    mgr = _login(client, "manager@test.example")
    rows = client.get("/api/v1/team/clients", headers=mgr).json()
    row = next(r for r in rows if r["id"] == elder.id)
    assert row["mine"] is True
    assert row["needs_first_assessment"] is True and row["assessment_overdue"] is False
    assert row["next_visit_at"] and row["open_alerts"] == 0
    assert "kushlife_status" in row and "score" in row


def test_client_list_query_count_is_constant(client, db, seed_tenant):
    from sqlalchemy import event

    admin = _login(client, "admin@test.example")
    engine = db.get_bind()
    counts = []
    live = {"n": 0}

    def count(*_a, **_k):
        live["n"] += 1

    event.listen(engine, "before_cursor_execute", count)
    try:
        for n in (2, 20):
            existing = db.query(Elder).count()
            for i in range(existing, n):
                db.add(Elder(tenant_id=seed_tenant["tenant"].id, first_name=f"C{i}", last_name="X", status="ACTIVE"))
            db.commit()
            live["n"] = 0
            rows = client.get("/api/v1/team/clients", headers=admin).json()
            counts.append(live["n"])
            assert len(rows) >= n
    finally:
        event.remove(engine, "before_cursor_execute", count)
    assert 0 < counts[0] == counts[1], counts
    assert counts[1] < 30, counts


def test_client_list_open_sos_requests_messages_badges(client, db, seed_tenant):
    from app.models.incident import Incident

    elder, outside = _mine_and_outside(db, seed_tenant)
    now = datetime.now(timezone.utc)
    for sev, status in (("critical", "open"), ("warning", "open"), ("critical", "resolved")):
        db.add(Incident(tenant_id=elder.tenant_id, elder_id=elder.id, kind="sos_button", severity=sev,
                        status=status, source="device", opened_at=now))
    elder.custom_attributes = {
        "safe_home": {
            "service_requests": [
                {"id": "r1", "service_type": "other", "status": "requested"},
                {"id": "r2", "service_type": "other", "status": "done"},
            ],
            "family_hub": {
                "messages": [
                    {"id": "m1", "sender_role": "family", "body": "Hi", "created_at": now.isoformat()},
                    {"id": "m2", "sender_role": "staff", "body": "Hello", "created_at": now.isoformat()},
                ],
            },
        }
    }
    db.commit()
    mgr = _login(client, "manager@test.example")
    rows = client.get("/api/v1/team/clients", headers=mgr).json()
    row = next(r for r in rows if r["id"] == elder.id)
    assert row["open_alerts"] == 2 and row["open_sos"] == 1
    assert row["open_requests"] == 1
    assert row["unread_messages"] == 1
    assert row["reassessment_due"] is True  # never assessed, nothing booked
    # Team scope: the manager does not see the other manager's client.
    assert all(r["id"] != outside.id for r in rows) or next(r for r in rows if r["id"] == outside.id)["open_sos"] == 0
