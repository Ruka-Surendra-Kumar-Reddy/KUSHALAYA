"""Client care team: care manager change (admin only), regular caregivers add /
replace / remove (team-scoped), moving visits on replace, audit trail, bulk."""

from datetime import timedelta

import pytest

from app.core.security import hash_password
from app.livewell import care_jobs
from app.livewell import care_team as ct
from app.livewell.care_series import ist_today
from app.models.assignment import Assignment
from app.models.care_job import CareJob
from app.models.caregiver import Caregiver
from app.models.client_care import HandoverNote
from app.models.elder import Elder
from app.models.leave_request import LeaveRequest
from app.models.user import User

C = "/api/v1/home-safety/clients"


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def told(monkeypatch):
    sent: list[tuple[int, str, str]] = []
    monkeypatch.setattr(
        care_jobs, "_notify_family", lambda db, elder, title, body, event="visit": sent.append((elder.id, title, body))
    )
    return sent


@pytest.fixture
def mailed(monkeypatch):
    sent: list[tuple[str, int]] = []
    monkeypatch.setattr(ct, "_notify_manager", lambda db, elder, to, by, note: sent.append((to.email, elder.id)))
    return sent


def _user(db, tenant_id, email, role, **extra):
    u = User(email=email, password_hash=hash_password("testpass123"), first_name=email.split("@")[0].title(),
             last_name="", role=role, tenant_id=tenant_id, **extra)
    db.add(u)
    db.commit()
    return u


def _cg(db, tenant_id, manager_id, first):
    cg = Caregiver(tenant_id=tenant_id, first_name=first, last_name="Test", manager_user_id=manager_id, phone="+91 90000 00000")
    db.add(cg)
    db.commit()
    return cg


def _assign(db, elder, cg):
    a = Assignment(tenant_id=elder.tenant_id, elder_id=elder.id, caregiver_id=cg.id, status="ACTIVE", start_date=ist_today())
    db.add(a)
    db.commit()
    return a


def _job(client, headers, elder_id, cg_id, days=3, hour=10):
    at = f"{(ist_today() + timedelta(days=days)).isoformat()}T{hour:02d}:00:00+05:30"
    res = client.post("/api/v1/jobs", json={"elder_id": elder_id, "caregiver_id": cg_id, "scheduled_at": at,
                                            "duration_minutes": 60, "title": "Visit"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_admin_changes_manager_with_handover_notice_and_audit(client, db, seed_tenant, told, mailed):
    t, elder = seed_tenant["tenant"], seed_tenant["elder"]
    new = _user(db, t.id, "priya@test.example", "CARE_MANAGER")
    admin = _login(client, "admin@test.example")
    res = client.put(f"{C}/{elder.id}/care-team/manager", json={"manager_user_id": new.id, "note": "Diabetic, morning visits"}, headers=admin)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["manager"]["id"] == new.id and body["manager"]["email"] == "priya@test.example"
    db.expire_all()
    assert db.get(Elder, elder.id).manager_user_id == new.id
    h = db.query(HandoverNote).filter(HandoverNote.elder_id == elder.id).one()
    assert h.kind == "client_move" and h.to_user_id == new.id and h.note == "Diabetic, morning visits"
    assert mailed == [("priya@test.example", elder.id)]
    assert body["recent_changes"][0]["action"] == "client_manager_changed"
    assert "Priya" in body["recent_changes"][0]["what"] and body["recent_changes"][0]["at_label"]
    # Old manager no longer sees the client (nothing else ties them).
    assert client.get(f"{C}/{elder.id}/care-team", headers=_login(client, "manager@test.example")).status_code == 404


def test_manager_cannot_change_manager(client, db, seed_tenant, mailed):
    t, elder = seed_tenant["tenant"], seed_tenant["elder"]
    new = _user(db, t.id, "priya@test.example", "CARE_MANAGER")
    mgr = _login(client, "manager@test.example")
    res = client.put(f"{C}/{elder.id}/care-team/manager", json={"manager_user_id": new.id}, headers=mgr)
    assert res.status_code == 403
    got = client.get(f"{C}/{elder.id}/care-team", headers=mgr).json()
    assert got["can_change_manager"] is False and got["can_edit_caregivers"] is True


def test_manager_assigns_within_team_only(client, db, seed_tenant):
    t, elder, mgr_user = seed_tenant["tenant"], seed_tenant["elder"], seed_tenant["manager"]
    other_mgr = _user(db, t.id, "other@test.example", "CARE_MANAGER")
    mine = _cg(db, t.id, mgr_user.id, "Asha")
    theirs = _cg(db, t.id, other_mgr.id, "Bina")
    outside = Elder(tenant_id=t.id, first_name="Out", last_name="Side", care_level="Low", manager_user_id=other_mgr.id)
    db.add(outside)
    db.commit()
    mgr = _login(client, "manager@test.example")
    res = client.post(f"{C}/{elder.id}/care-team/caregivers", json={"caregiver_id": mine.id}, headers=mgr)
    assert res.status_code == 201, res.text
    row = res.json()["caregivers"][0]
    assert row["name"] == "Asha Test" and row["phone"] and row["since"] == ist_today().isoformat()
    assert client.post(f"{C}/{elder.id}/care-team/caregivers", json={"caregiver_id": theirs.id}, headers=mgr).status_code == 400
    assert client.post(f"{C}/{outside.id}/care-team/caregivers", json={"caregiver_id": mine.id}, headers=mgr).status_code == 404
    # Duplicate is refused.
    assert client.post(f"{C}/{elder.id}/care-team/caregivers", json={"caregiver_id": mine.id}, headers=mgr).status_code == 400


def test_remove_ends_assignment_keeps_history(client, db, seed_tenant):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    a = _assign(db, elder, cg)
    admin = _login(client, "admin@test.example")
    res = client.delete(f"{C}/{elder.id}/care-team/caregivers/{a.id}", headers=admin)
    assert res.status_code == 200 and res.json()["caregivers"] == []
    db.expire_all()
    row = db.get(Assignment, a.id)
    assert row.status == "INACTIVE" and row.end_date == ist_today()
    assert res.json()["recent_changes"][0]["action"] == "care_team_caregiver_removed"


def test_replace_without_moving_visits(client, db, seed_tenant, told):
    t, elder, cg = seed_tenant["tenant"], seed_tenant["elder"], seed_tenant["caregiver"]
    new = _cg(db, t.id, seed_tenant["manager"].id, "Asha")
    a = _assign(db, elder, cg)
    admin = _login(client, "admin@test.example")
    jid = _job(client, admin, elder.id, cg.id)
    told.clear()
    res = client.post(f"{C}/{elder.id}/care-team/caregivers/{a.id}/replace",
                      json={"caregiver_id": new.id, "move_visits": False}, headers=admin)
    assert res.status_code == 200, res.text
    body = res.json()
    assert [c["caregiver_id"] for c in body["caregivers"]] == [new.id] and body["moved_visits"] == 0
    db.expire_all()
    assert db.get(CareJob, jid).caregiver_id == cg.id
    assert told and told[-1][1] == "Change of caregiver" and "Asha" in told[-1][2]
    assert body["recent_changes"][0]["action"] == "care_team_caregiver_replaced"


def test_replace_moves_visits_and_reports_clashes(client, db, seed_tenant, told):
    t, elder, cg = seed_tenant["tenant"], seed_tenant["elder"], seed_tenant["caregiver"]
    new = _cg(db, t.id, seed_tenant["manager"].id, "Asha")
    a = _assign(db, elder, cg)
    admin = _login(client, "admin@test.example")
    ok = _job(client, admin, elder.id, cg.id, days=3)
    busy = _job(client, admin, elder.id, cg.id, days=4)
    db.add(LeaveRequest(tenant_id=t.id, caregiver_id=new.id, start_date=ist_today() + timedelta(days=4),
                        end_date=ist_today() + timedelta(days=4), status="APPROVED", leave_type="CASUAL"))
    db.commit()
    told.clear()
    res = client.post(f"{C}/{elder.id}/care-team/caregivers/{a.id}/replace",
                      json={"caregiver_id": new.id, "move_visits": True}, headers=admin)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["moved_visits"] == 1
    assert len(body["clashes"]) == 1 and body["clashes"][0]["job_id"] == busy and "leave" in body["clashes"][0]["reason"]
    db.expire_all()
    assert db.get(CareJob, ok).caregiver_id == new.id
    assert db.get(CareJob, busy).caregiver_id == cg.id
    assert [x[1] for x in told] == ["Change of caregiver"]  # family told once


def test_caregiver_and_family_get_403(client, db, seed_tenant):
    t, elder, cg = seed_tenant["tenant"], seed_tenant["elder"], seed_tenant["caregiver"]
    _user(db, t.id, "cg.login@test.example", "CAREGIVER", caregiver_id=cg.id)
    _user(db, t.id, "fam@test.example", "ELDER_PORTAL", elder_id=elder.id)
    for email in ("cg.login@test.example", "fam@test.example"):
        h = _login(client, email)
        assert client.get(f"{C}/{elder.id}/care-team", headers=h).status_code == 403
        assert client.post(f"{C}/{elder.id}/care-team/caregivers", json={"caregiver_id": cg.id}, headers=h).status_code == 403
        assert client.post("/api/v1/team/clients/bulk-care-team", json={"elder_ids": [elder.id], "action": "caregiver", "caregiver_id": cg.id}, headers=h).status_code == 403


def test_bulk_actions_and_client_list(client, db, seed_tenant, mailed):
    t, elder, cg = seed_tenant["tenant"], seed_tenant["elder"], seed_tenant["caregiver"]
    second = Elder(tenant_id=t.id, first_name="Two", last_name="Client", care_level="Low", manager_user_id=seed_tenant["manager"].id)
    db.add(second)
    db.commit()
    _assign(db, second, cg)  # already on second's team -> reported as a failure
    new = _user(db, t.id, "priya@test.example", "CARE_MANAGER")
    admin = _login(client, "admin@test.example")
    res = client.post("/api/v1/team/clients/bulk-care-team",
                      json={"elder_ids": [elder.id, second.id], "action": "caregiver", "caregiver_id": cg.id}, headers=admin)
    assert res.status_code == 200, res.text
    out = res.json()
    assert [d["elder_id"] for d in out["done"]] == [elder.id]
    assert out["failed"][0]["elder_id"] == second.id and "already" in out["failed"][0]["reason"]
    mgr = _login(client, "manager@test.example")
    assert client.post("/api/v1/team/clients/bulk-care-team",
                       json={"elder_ids": [elder.id], "action": "manager", "manager_user_id": new.id}, headers=mgr).status_code == 403
    res = client.post("/api/v1/team/clients/bulk-care-team",
                      json={"elder_ids": [elder.id, second.id], "action": "manager", "manager_user_id": new.id}, headers=admin)
    assert len(res.json()["done"]) == 2 and len(mailed) == 2
    rows = {r["id"]: r for r in client.get("/api/v1/team/clients", headers=admin).json()}
    assert rows[elder.id]["manager"] == {"id": new.id, "name": "Priya"}
    assert rows[elder.id]["caregivers"] == [{"id": cg.id, "name": "Care Giver"}]
    theirs = client.get(f"/api/v1/team/caregivers/{cg.id}/clients", headers=admin).json()
    assert {c["elder_id"] for c in theirs} == {elder.id, second.id}
