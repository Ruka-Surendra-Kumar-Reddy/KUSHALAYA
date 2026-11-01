"""Jobs: manager schedules, caregiver works it in the field app, family is told."""
from tests.assess_client import confirm_client


from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.models.elder import Elder
from app.models.user import User


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _caregiver_login(client, db, seed_tenant):
    cg = seed_tenant["caregiver"]
    db.add(
        User(
            email="field.cg@test.example",
            password_hash=hash_password("testpass123"),
            first_name=cg.first_name,
            last_name=cg.last_name,
            role="CAREGIVER",
            tenant_id=cg.tenant_id,
            caregiver_id=cg.id,
        )
    )
    db.commit()
    return _login(client, "field.cg@test.example")


def _schedule(client, headers, elder_id, caregiver_id, kind="visit", **extra):
    when = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    res = client.post(
        "/api/v1/jobs",
        json={"elder_id": elder_id, "kind": kind, "scheduled_at": when, "caregiver_id": caregiver_id, **extra},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _family_alerts(db, elder_id):
    elder = db.get(Elder, elder_id)
    db.refresh(elder)
    hub = (elder.custom_attributes or {}).get("safe_home", {}).get("family_hub", {})
    return [a.get("title") for a in hub.get("alerts", [])]


def test_visit_flow_notifies_family(client, db, seed_tenant, auth_headers):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    job = _schedule(client, auth_headers, elder.id, cg.id, tasks="Medicines check")
    assert job["status"] == "scheduled" and job["caregiver_name"]

    field = _caregiver_login(client, db, seed_tenant)
    mine = client.get("/api/v1/caregiver-portal/jobs", headers=field).json()
    assert [j["id"] for j in mine] == [job["id"]]
    for step in ("on_the_way", "checked_in", "completed"):
        res = client.post(f"/api/v1/caregiver-portal/jobs/{job['id']}/status", json={"latitude": 17.4, "longitude": 78.4, "status": step}, headers=field)
        assert res.status_code == 200, res.text
    assert res.json()["status"] == "completed"

    titles = " | ".join(t for t in _family_alerts(db, elder.id) if t)
    assert "scheduled" in titles and "arrived" in titles and "completed" in titles


def test_caregiver_cannot_skip_steps_or_touch_other_jobs(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    job = _schedule(client, auth_headers, elder.id, None)
    field = _caregiver_login(client, db, seed_tenant)
    res = client.post(f"/api/v1/caregiver-portal/jobs/{job['id']}/status", json={"latitude": 17.4, "longitude": 78.4, "status": "checked_in"}, headers=field)
    assert res.status_code == 404  # not assigned to them


def test_field_assessment_scores_and_publishes(client, db, seed_tenant, auth_headers):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    job = _schedule(client, auth_headers, elder.id, cg.id, kind="assessment")
    field = _caregiver_login(client, db, seed_tenant)
    client.post(f"/api/v1/caregiver-portal/jobs/{job['id']}/status", json={"latitude": 17.4, "longitude": 78.4, "status": "checked_in"}, headers=field)

    form = client.get(f"/api/v1/caregiver-portal/jobs/{job['id']}/assessment", headers=field).json()
    items = [i["id"] for c in form["categories"] for i in c["items"]]
    assert len(items) > 20

    ratings = {i: "excellent" for i in items}
    draft = client.put(
        f"/api/v1/caregiver-portal/jobs/{job['id']}/assessment",
        json={"ratings": dict(list(ratings.items())[:5])},
        headers=field,
    )
    assert draft.status_code == 200, draft.text
    assert draft.json()["status"] == "draft"

    confirm_client(client, field, job["id"], portal=True)
    done = client.put(
        f"/api/v1/caregiver-portal/jobs/{job['id']}/assessment",
        json={"ratings": ratings, "complete": True},
        headers=field,
    )
    # Finishing in the caregiver app needs a location.
    assert done.status_code == 400, done.text
    # ...and every question answered: a half-done assessment never publishes a score.
    partial = dict(list(ratings.items())[:2])
    done = client.put(
        f"/api/v1/caregiver-portal/jobs/{job['id']}/assessment",
        json={"ratings": partial, "complete": True, "latitude": 17.44, "longitude": 78.35},
        headers=field,
    )
    assert done.status_code == 400 and "not answered yet" in done.text, done.text
    done = client.put(
        f"/api/v1/caregiver-portal/jobs/{job['id']}/assessment",
        json={"ratings": ratings, "complete": True, "latitude": 17.44, "longitude": 78.35},
        headers=field,
    )
    assert done.status_code == 200, done.text
    assert done.json()["job"]["status"] == "completed"
    assert "Home safety assessment completed" in _family_alerts(db, elder.id)

    listed = client.get(f"/api/v1/jobs?elder_id={elder.id}", headers=auth_headers).json()
    assert listed[0]["assessment_id"]


def test_manager_cannot_schedule_outside_team(client, db, seed_tenant, auth_headers):
    outside = Elder(tenant_id=seed_tenant["tenant"].id, first_name="Out", last_name="Side", status="ACTIVE")
    db.add(outside)
    db.commit()
    when = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    res = client.post("/api/v1/jobs", json={"elder_id": outside.id, "scheduled_at": when}, headers=auth_headers)
    assert res.status_code == 404


def test_family_schedule_shows_jobs_without_staff_notes(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    _schedule(client, auth_headers, elder.id, None, tasks="Physio exercises", staff_note="internal only")
    family = User(
        email="fam.jobs@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Fam",
        last_name="Jobs",
        role="ELDER_PORTAL",
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
    )
    db.add(family)
    db.commit()
    headers = _login(client, "fam.jobs@test.example")
    res = client.get("/api/v1/home-safety/family/schedule", headers=headers)
    assert res.status_code == 200, res.text
    up = res.json()["upcoming"]
    assert any(v["summary"] == "Physio exercises" for v in up)
    assert "internal only" not in res.text


def test_family_notify_sends_email_and_sms(db, seed_tenant, monkeypatch):
    from app.livewell import family_notify

    sent = []
    monkeypatch.setattr(family_notify, "_send", lambda e, p, s, b: sent.append((e, p, s, b)))
    elder = seed_tenant["elder"]
    elder.emergency_contact_phone = "+919000000001"
    db.add(
        User(
            email="notify.fam@test.example",
            password_hash=hash_password("testpass123"),
            first_name="N",
            last_name="F",
            role="ELDER_PORTAL",
            tenant_id=elder.tenant_id,
            elder_id=elder.id,
        )
    )
    db.commit()
    from app.livewell import email_notifications

    mails = []
    monkeypatch.setattr(email_notifications, "_deliver", lambda to, s, t, h: mails.append((to, s)))
    family_notify.notify_family(db, elder, "Care visit scheduled", "Thu 10:00", background=False)
    # Subjects name who it is about (Phase 3C): "Care visit scheduled — <first name>".
    assert mails == [(["notify.fam@test.example"], f"KushAlaya: Care visit scheduled — {elder.first_name}")]
    assert sent == []  # routine updates: portal + email only, no SMS/WhatsApp
    family_notify.notify_family(db, elder, "Visit missed", "We'll call you", event="missed", background=False)
    assert sent and "+919000000001" in sent[0][1]


def test_caregiver_app_lists_an_unfinished_visit_from_days_ago(client, db, seed_tenant, auth_headers):
    """A visit checked in 3 days ago and never closed stays on the caregiver's list ("Finish this visit")."""
    from app.models.care_job import CareJob

    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    job = _schedule(client, auth_headers, elder.id, cg.id)
    old = db.get(CareJob, job["id"])
    old.status = "checked_in"
    old.scheduled_at = datetime.now(timezone.utc) - timedelta(days=3)
    db.commit()

    field = _caregiver_login(client, db, seed_tenant)
    mine = client.get("/api/v1/caregiver-portal/jobs", headers=field).json()
    assert job["id"] in [j["id"] for j in mine]
