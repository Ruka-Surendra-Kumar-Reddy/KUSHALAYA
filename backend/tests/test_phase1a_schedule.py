"""Schedule phase 1A: the family request follows its job, double-booking, status rules."""

from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.livewell.daily_checks import mark_missed_visits
from app.livewell.family_elder_access import ensure_family_elder_link
from app.models.care_job import CareJob
from app.models.elder import Elder
from app.models.user import User

F = "/api/v1/home-safety/family"


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _family(client, db, elder):
    user = User(
        email="family.p1a@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Fam",
        last_name="P1a",
        role="ELDER_PORTAL",
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
    )
    db.add(user)
    db.flush()
    ensure_family_elder_link(db, user, elder)
    db.commit()
    return _login(client, user.email)


def _at(hours: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _book(client, headers, elder_id, cg_id=None, hours=2.0, **extra):
    return client.post(
        "/api/v1/jobs",
        json={"elder_id": elder_id, "kind": "visit", "scheduled_at": _at(hours), "caregiver_id": cg_id, **extra},
        headers=headers,
    )


def _request(db, elder_id, request_id):
    elder = db.get(Elder, elder_id)
    db.refresh(elder)
    rows = elder.custom_attributes["safe_home"]["service_requests"]
    return next(r for r in rows if r["id"] == request_id)


def _requested_job(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    fam = _family(client, db, elder)
    req = client.post(f"{F}/service-requests", headers=fam, json={"service_type": "care_visit"}).json()
    res = _book(client, auth_headers, elder.id, request_id=req["id"])
    assert res.status_code == 201, res.text
    assert _request(db, elder.id, req["id"])["status"] == "confirmed"
    return fam, req, res.json()


def test_request_done_when_job_completed(client, db, seed_tenant, auth_headers):
    _, req, job = _requested_job(client, db, seed_tenant, auth_headers)
    client.post(f"/api/v1/jobs/{job['id']}/progress", json={"status": "checked_in"}, headers=auth_headers)
    checks = {k: {"status": "ok"} for k in ("safe", "steady", "settled", "connected")}
    res = client.post(f"/api/v1/jobs/{job['id']}/report", json={"kushlife": {"checks": checks}}, headers=auth_headers)
    assert res.status_code == 200, res.text
    assert _request(db, job["elder_id"], req["id"])["status"] == "done"


def test_request_back_to_requested_when_job_cancelled(client, db, seed_tenant, auth_headers):
    _, req, job = _requested_job(client, db, seed_tenant, auth_headers)
    res = client.patch(f"/api/v1/jobs/{job['id']}", json={"status": "cancelled"}, headers=auth_headers)
    assert res.status_code == 200, res.text
    r = _request(db, job["elder_id"], req["id"])
    assert r["status"] == "requested"
    assert r["staff_note"] == "We'll rebook this"
    attn = client.get("/api/v1/home-safety/dashboard/attention", headers=auth_headers).json()
    assert req["id"] in [x["id"] for x in attn["requests"]]


def test_missed_job_reopens_request_and_family_sees_didnt_happen(client, db, seed_tenant, auth_headers):
    fam, req, job = _requested_job(client, db, seed_tenant, auth_headers)
    row = db.get(CareJob, job["id"])
    row.scheduled_at = datetime.now(timezone.utc) - timedelta(hours=5)
    db.commit()
    assert job["id"] in mark_missed_visits(db)
    assert _request(db, job["elder_id"], req["id"])["status"] == "requested"
    visits = client.get(f"{F}/schedule", headers=fam)
    assert visits.status_code == 200, visits.text
    body = visits.json()
    rows = body if isinstance(body, list) else [*body.get("recent", []), *body.get("upcoming", []), *body.get("visits", [])]
    mine = [v for v in rows if v.get("id") == f"job-{job['id']}"]
    assert mine and mine[0]["status"] == "Didn't happen"


def test_family_cancel_cancels_job(client, db, seed_tenant, auth_headers):
    fam, req, job = _requested_job(client, db, seed_tenant, auth_headers)
    res = client.post(f"{F}/service-requests/{req['id']}/cancel", headers=fam)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "cancelled"
    db.expire_all()
    assert db.get(CareJob, job["id"]).status == "cancelled"
    # The request stays cancelled (it does not bounce back to "requested").
    assert _request(db, job["elder_id"], req["id"])["status"] == "cancelled"


def test_double_booking_needs_force(client, seed_tenant, auth_headers):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    assert _book(client, auth_headers, elder.id, cg.id, hours=3).status_code == 201
    clash = _book(client, auth_headers, elder.id, cg.id, hours=3.5)
    assert clash.status_code == 409
    msg = clash.json().get("detail") or clash.json().get("error") or clash.text
    assert cg.first_name in msg and "Book anyway?" in msg
    assert _book(client, auth_headers, elder.id, cg.id, hours=3.5, force=True).status_code == 201
    # Later the same day is fine.
    assert _book(client, auth_headers, elder.id, cg.id, hours=6).status_code == 201


def test_second_open_assessment_needs_force(client, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    assert _book(client, auth_headers, elder.id, kind="assessment").status_code == 201
    assert _book(client, auth_headers, elder.id, hours=30, kind="assessment").status_code == 409


def test_reschedule_into_clash_is_409(client, seed_tenant, auth_headers):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    _book(client, auth_headers, elder.id, cg.id, hours=3)
    other = _book(client, auth_headers, elder.id, cg.id, hours=8).json()
    res = client.patch(f"/api/v1/jobs/{other['id']}", json={"scheduled_at": _at(3)}, headers=auth_headers)
    assert res.status_code == 409
    res = client.patch(f"/api/v1/jobs/{other['id']}", json={"scheduled_at": _at(3), "force": True}, headers=auth_headers)
    assert res.status_code == 200


def test_status_transitions(client, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    job = _book(client, auth_headers, elder.id).json()
    # On the way can still be rescheduled or cancelled.
    client.post(f"/api/v1/jobs/{job['id']}/progress", json={"status": "on_the_way"}, headers=auth_headers)
    assert client.patch(f"/api/v1/jobs/{job['id']}", json={"scheduled_at": _at(5)}, headers=auth_headers).status_code == 200
    assert client.patch(f"/api/v1/jobs/{job['id']}", json={"status": "cancelled"}, headers=auth_headers).status_code == 200
    # Cancelled is final.
    for patch in ({"status": "scheduled"}, {"status": "completed"}, {"scheduled_at": _at(9)}):
        assert client.patch(f"/api/v1/jobs/{job['id']}", json=patch, headers=auth_headers).status_code == 400
    # A scheduled job can't jump straight to completed.
    other = _book(client, auth_headers, elder.id, hours=20).json()
    assert client.patch(f"/api/v1/jobs/{other['id']}", json={"status": "completed"}, headers=auth_headers).status_code == 400


def test_booking_a_cancelled_request_does_not_revive_it(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    fam = _family(client, db, elder)
    req = client.post(f"{F}/service-requests", headers=fam, json={"service_type": "care_visit"}).json()
    client.post(f"{F}/service-requests/{req['id']}/cancel", headers=fam)
    res = _book(client, auth_headers, elder.id, request_id=req["id"])
    assert res.status_code == 201, res.text
    assert res.json()["request_id"] is None and res.json()["note"]
    assert _request(db, elder.id, req["id"])["status"] == "cancelled"


def test_rebooked_missed_job_leaves_schedule(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    missed = _book(client, auth_headers, elder.id).json()
    row = db.get(CareJob, missed["id"])
    row.scheduled_at = datetime.now(timezone.utc) - timedelta(hours=5)
    row.created_at = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()
    mark_missed_visits(db)
    ids = [j["id"] for j in client.get("/api/v1/jobs", headers=auth_headers).json()]
    assert missed["id"] in ids
    # A different kind doesn't count as the rebooking.
    _book(client, auth_headers, elder.id, kind="install")
    assert missed["id"] in [j["id"] for j in client.get("/api/v1/jobs", headers=auth_headers).json()]
    _book(client, auth_headers, elder.id, hours=24)
    assert missed["id"] not in [j["id"] for j in client.get("/api/v1/jobs", headers=auth_headers).json()]


def test_staff_rules_for_assessment_complete_and_missed(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    job = _book(client, auth_headers, elder.id, kind="assessment").json()
    client.post(f"/api/v1/jobs/{job['id']}/progress", json={"status": "checked_in"}, headers=auth_headers)
    res = client.patch(f"/api/v1/jobs/{job['id']}", json={"status": "completed"}, headers=auth_headers)
    assert res.status_code == 400 and "assessment" in res.text.lower()

    visit = _book(client, auth_headers, elder.id, hours=30).json()
    assert client.patch(f"/api/v1/jobs/{visit['id']}", json={"status": "missed"}, headers=auth_headers).status_code == 200
    e = db.get(Elder, elder.id)
    db.refresh(e)
    alerts = [a.get("title", "") for a in e.custom_attributes["safe_home"]["family_hub"]["alerts"]]
    assert any("didn’t happen" in t for t in alerts)
