"""Phase 4C: incident reports (#97) and the per-client visit checklist (#99)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import hash_password
from app.livewell import email_notifications as en
from app.models.caregiver import Caregiver
from app.models.user import User

OK4 = {"safe": "ok", "steady": "ok", "settled": "ok", "connected": "ok"}


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _user(db, email, role, **kw):
    db.add(User(email=email, password_hash=hash_password("testpass123"), first_name="U", last_name=role[:3],
                role=role, **kw))
    db.commit()


def _cg(client, db, seed_tenant):
    cg = seed_tenant["caregiver"]
    _user(db, "p4c.cg@test.example", "CAREGIVER", tenant_id=cg.tenant_id, caregiver_id=cg.id)
    return _login(client, "p4c.cg@test.example")


def _job(client, headers, elder_id, cg_id):
    when = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    res = client.post("/api/v1/jobs", json={"elder_id": elder_id, "kind": "visit", "scheduled_at": when,
                                            "caregiver_id": cg_id}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


@pytest.fixture
def mails(monkeypatch):
    out: list[tuple[str, str, str]] = []
    real_send = en.send
    monkeypatch.setattr(en, "_deliver", lambda to, s, t, h: out.extend((x, s, t) for x in to))
    monkeypatch.setattr(
        en, "send", lambda to, title, body, *, family, background=True: real_send(to, title, body, family=family, background=False)
    )
    return out


FALL = {"kind": "fall", "what_happened": "Slipped in the bathroom", "location": "Bathroom",
        "injury": "Bruised left hip", "action_taken": "Helped up, ice pack", "family_informed": True}


def test_caregiver_files_only_on_own_visits(client, db, seed_tenant, auth_headers):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    mine = _job(client, auth_headers, elder.id, cg.id)
    other = Caregiver(tenant_id=elder.tenant_id, first_name="Other", last_name="Cg",
                      manager_user_id=seed_tenant["manager"].id)
    db.add(other)
    db.commit()
    theirs = _job(client, auth_headers, elder.id, other.id)
    field = _cg(client, db, seed_tenant)

    res = client.post(f"/api/v1/caregiver-portal/jobs/{theirs['id']}/incident", json=FALL, headers=field)
    assert res.status_code == 404
    res = client.post(f"/api/v1/caregiver-portal/jobs/{mine['id']}/incident",
                      json={**FALL, "kind": "near_miss", "injury": ""}, headers=field)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["care_job_id"] == mine["id"] and body["status"] == "open" and not body["serious"]
    assert "staff_notes" not in body
    # Family cannot use the caregiver route.
    _user(db, "p4c.fam0@test.example", "ELDER_PORTAL", tenant_id=elder.tenant_id, elder_id=elder.id)
    fam = _login(client, "p4c.fam0@test.example")
    assert client.post(f"/api/v1/caregiver-portal/jobs/{mine['id']}/incident", json=FALL, headers=fam).status_code == 403


def test_serious_notifies_and_needs_attention_until_reviewed(client, db, seed_tenant, auth_headers, mails):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    job = _job(client, auth_headers, elder.id, cg.id)
    field = _cg(client, db, seed_tenant)
    res = client.post(f"/api/v1/caregiver-portal/jobs/{job['id']}/incident", json=FALL, headers=field)
    assert res.status_code == 201, res.text
    rep = res.json()
    assert rep["serious"] is True
    assert any(to == "manager@test.example" and "Serious incident" in s for to, s, _ in mails)

    attn = client.get("/api/v1/home-safety/dashboard/attention", headers=auth_headers).json()
    assert [i["id"] for i in attn["incidents"]] == [rep["id"]]
    assert attn["counts"]["incidents"] == 1

    res = client.post(f"/api/v1/home-safety/incident-reports/{rep['id']}/review",
                      json={"staff_notes": "Caregiver late to respond"}, headers=auth_headers)
    assert res.status_code == 200 and res.json()["status"] == "reviewed"
    attn = client.get("/api/v1/home-safety/dashboard/attention", headers=auth_headers).json()
    assert attn["incidents"] == []

    # Medication error is always serious; a near-miss is not.
    med = client.post("/api/v1/home-safety/incident-reports", json={
        "elder_id": elder.id, "kind": "medication_error", "what_happened": "Evening dose given twice"},
        headers=auth_headers).json()
    assert med["serious"] is True


def test_family_sees_only_reviewed_plain_summary(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    _user(db, "p4c.fam@test.example", "ELDER_PORTAL", tenant_id=elder.tenant_id, elder_id=elder.id)
    fam = _login(client, "p4c.fam@test.example")
    rep = client.post("/api/v1/home-safety/incident-reports", json={**FALL, "elder_id": elder.id},
                      headers=auth_headers).json()
    assert client.get("/api/v1/home-safety/family/incident-reports", headers=fam).json() == []

    client.post(f"/api/v1/home-safety/incident-reports/{rep['id']}/review", json={
        "staff_notes": "SECRET staff note", "family_summary": "Amma slipped; we added a bath mat."}, headers=auth_headers)
    rows = client.get("/api/v1/home-safety/family/incident-reports", headers=fam).json()
    assert len(rows) == 1 and rows[0]["summary"] == "Amma slipped; we added a bath mat."
    flat = str(rows)
    assert "SECRET" not in flat and "Bruised" not in flat and "staff_notes" not in flat


def test_close_requires_outcome_and_counts(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    rep = client.post("/api/v1/home-safety/incident-reports", json={
        **FALL, "elder_id": elder.id,
        "follow_ups": [{"action": "Fit grab bar", "owner": "Ravi", "due_date": "2026-10-20"}]},
        headers=auth_headers).json()
    assert rep["follow_ups"][0]["owner"] == "Ravi"
    res = client.post(f"/api/v1/home-safety/incident-reports/{rep['id']}/close", json={"outcome": " "},
                      headers=auth_headers)
    assert res.status_code == 400
    res = client.post(f"/api/v1/home-safety/incident-reports/{rep['id']}/close",
                      json={"outcome": "Grab bar fitted, no further falls"}, headers=auth_headers)
    assert res.status_code == 200 and res.json()["status"] == "closed" and res.json()["reviewed_at"]
    lst = client.get(f"/api/v1/home-safety/incident-reports?elder_id={elder.id}", headers=auth_headers).json()
    assert lst["counts"]["falls"] == 1 and lst["counts"]["open"] == 0


def test_team_scope(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    rep = client.post("/api/v1/home-safety/incident-reports", json={**FALL, "elder_id": elder.id},
                      headers=auth_headers).json()
    _user(db, "p4c.mgr2@test.example", "CARE_MANAGER", tenant_id=elder.tenant_id)
    other = _login(client, "p4c.mgr2@test.example")
    assert client.get("/api/v1/home-safety/incident-reports", headers=other).json()["reports"] == []
    assert client.get(f"/api/v1/home-safety/incident-reports/{rep['id']}", headers=other).status_code == 404
    assert client.post(f"/api/v1/home-safety/incident-reports/{rep['id']}/review", headers=other).status_code == 404
    assert client.post("/api/v1/home-safety/incident-reports", json={**FALL, "elder_id": elder.id},
                       headers=other).status_code == 404
    assert client.get(f"/api/v1/home-safety/clients/{elder.id}/visit-checklist", headers=other).status_code == 404
    attn = client.get("/api/v1/home-safety/dashboard/attention", headers=other).json()
    assert attn["incidents"] == []


def test_checklist_saved_with_visit_and_in_report(client, db, seed_tenant, auth_headers):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    res = client.put(f"/api/v1/home-safety/clients/{elder.id}/visit-checklist", json={"items": [
        {"label": "Give 9am medicines"}, {"label": "Check feet"}, {"label": "Walk 10 min"}]}, headers=auth_headers)
    assert res.status_code == 200, res.text
    items = res.json()["items"]
    assert [i["label"] for i in items] == ["Give 9am medicines", "Check feet", "Walk 10 min"]
    got = client.get(f"/api/v1/home-safety/clients/{elder.id}/visit-checklist", headers=auth_headers).json()
    assert "suggestions" in got

    job = _job(client, auth_headers, elder.id, cg.id)
    field = _cg(client, db, seed_tenant)
    jobs = client.get("/api/v1/caregiver-portal/jobs", headers=field).json()
    assert [i["label"] for i in jobs[0]["checklist"]] == [i["label"] for i in items]

    client.post(f"/api/v1/caregiver-portal/jobs/{job['id']}/status", json={"latitude": 17.4, "longitude": 78.4, "status": "checked_in"}, headers=field)
    done = client.post(f"/api/v1/caregiver-portal/jobs/{job['id']}/report", json={"latitude": 17.4, "longitude": 78.4, 
        "checks": OK4, "note": "Good day",
        "checklist": {items[0]["id"]: {"done": True}, items[1]["id"]: {"done": False, "reason": "She was asleep"}},
    }, headers=field)
    assert done.status_code == 200, done.text  # the unticked "Walk" item does not block
    saved = done.json()["report"]["checklist"]
    assert [r["done"] for r in saved] == [True, False, None]
    assert saved[1]["reason"] == "She was asleep"

    _user(db, "p4c.fam2@test.example", "ELDER_PORTAL", tenant_id=elder.tenant_id, elder_id=elder.id)
    fam = _login(client, "p4c.fam2@test.example")
    sched = client.get("/api/v1/home-safety/family/schedule", headers=fam).json()
    summary = next(v["summary"] for v in sched["recent"])
    assert "Visit checklist: 1 of 3 done" in summary and "Check feet (She was asleep)" in summary


def test_incident_time_with_offset_is_stored_as_utc(client, db, seed_tenant, auth_headers):
    from app.models.incident_report import IncidentReport

    elder = seed_tenant["elder"]
    res = client.post("/api/v1/home-safety/incident-reports", json={
        "elder_id": elder.id, "kind": "near_miss", "what_happened": "Nearly tripped on a rug",
        "occurred_at": "2026-10-01T10:00:00+05:30"}, headers=auth_headers)
    assert res.status_code == 201, res.text
    db.expire_all()
    row = db.get(IncidentReport, res.json()["id"])
    stored = row.occurred_at if row.occurred_at.tzinfo else row.occurred_at.replace(tzinfo=timezone.utc)
    assert stored == datetime(2026, 10, 1, 4, 30, tzinfo=timezone.utc)
