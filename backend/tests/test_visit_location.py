"""Visit location capture: required in the caregiver app, optional for ops staff,
stored on the job, and a closable alert to the manager + admins when far from home."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import hash_password
from app.livewell import visit_location
from app.models.care_job import CareJob
from app.models.elder_location import ElderLocation
from app.models.staff_alert import StaffAlert
from app.models.user import User

HOME = (17.4400, 78.3489)
NEAR = (17.4410, 78.3489)  # ~110 m north
FAR = (17.4400, 78.3700)  # ~2.2 km east
KUSHLIFE = {"checks": {"safe": "ok", "steady": "ok", "settled": "ok", "connected": "ok"}, "note": "All good"}


def _login(client, email):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def s(client, db, seed_tenant, auth_headers):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    elder.first_name, elder.last_name, elder.gender = "Lakshmi", "Reddy", "Female"
    db.add(
        User(
            email="loc.cg@test.example",
            password_hash=hash_password("testpass123"),
            first_name="Care",
            last_name="Giver",
            role="CAREGIVER",
            tenant_id=cg.tenant_id,
            caregiver_id=cg.id,
        )
    )
    db.commit()
    when = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    job = client.post(
        "/api/v1/jobs",
        json={"elder_id": elder.id, "kind": "visit", "scheduled_at": when, "caregiver_id": cg.id},
        headers=auth_headers,
    ).json()
    return {
        "job": job,
        "elder": elder,
        "cg": _login(client, "loc.cg@test.example"),
        "staff": auth_headers,
        "admin": _login(client, "admin@test.example"),
    }


def _pin(db, elder):
    db.add(ElderLocation(tenant_id=elder.tenant_id, elder_id=elder.id, latitude=HOME[0], longitude=HOME[1]))
    db.commit()


def _status(client, s, status, point=None, accuracy=None):
    body = {"status": status}
    if point:
        body.update(latitude=point[0], longitude=point[1], accuracy=accuracy)
    return client.post(f"/api/v1/caregiver-portal/jobs/{s['job']['id']}/status", json=body, headers=s["cg"])


def _alerts(db):
    return db.query(StaffAlert).order_by(StaffAlert.id).all()


def test_caregiver_check_in_and_finish_need_a_location(client, db, s):
    res = _status(client, s, "checked_in")
    assert res.status_code == 400 and "Turn on location to check in" in res.text
    assert _status(client, s, "checked_in", NEAR, 15).status_code == 200
    res = client.post(f"/api/v1/caregiver-portal/jobs/{s['job']['id']}/report", json=KUSHLIFE, headers=s["cg"])
    assert res.status_code == 400 and "Turn on location to finish" in res.text
    res = client.post(
        f"/api/v1/caregiver-portal/jobs/{s['job']['id']}/report",
        json={**KUSHLIFE, "latitude": FAR[0], "longitude": FAR[1], "accuracy": 20},
        headers=s["cg"],
    )
    assert res.status_code == 200, res.text
    job = db.get(CareJob, s["job"]["id"])
    db.refresh(job)
    assert (job.checkin_lat, job.checkin_lng, job.checkin_accuracy_m) == (NEAR[0], NEAR[1], 15)
    assert (job.checkout_lat, job.checkout_lng, job.checkout_accuracy_m) == (FAR[0], FAR[1], 20)


def test_far_check_in_alerts_manager_and_admins_once(client, db, s):
    _pin(db, s["elder"])
    assert _status(client, s, "checked_in", FAR, 10).status_code == 200
    rows = _alerts(db)
    assert len(rows) == 2  # the client's care manager + the one admin
    assert "Check-in for Lakshmi Reddy was 2.2 km from her home" in rows[0].body
    assert {r.dedupe_key for r in rows} == {f"visit_loc:{s['job']['id']}:checkin:{r.user_id}" for r in rows}

    # Same job and event again: the unique dedupe_key is respected, nothing added.
    job = db.get(CareJob, s["job"]["id"])
    visit_location.record(db, job, "checkin", *FAR, 10)
    db.commit()
    assert len(_alerts(db)) == 2

    # Each user sees theirs and closes it for themselves only.
    mine = client.get("/api/v1/jobs/location-alerts", headers=s["staff"]).json()
    assert len(mine) == 1 and mine[0]["title"] == "Check-in away from home"
    assert client.post(f"/api/v1/jobs/location-alerts/{mine[0]['id']}/dismiss", headers=s["admin"]).status_code == 404
    assert client.post(f"/api/v1/jobs/location-alerts/{mine[0]['id']}/dismiss", headers=s["staff"]).status_code == 200
    assert client.get("/api/v1/jobs/location-alerts", headers=s["staff"]).json() == []
    assert len(client.get("/api/v1/jobs/location-alerts", headers=s["admin"]).json()) == 1

    # Staff list shows the point and its distance; the family never gets it.
    item = next(j for j in client.get("/api/v1/jobs", headers=s["staff"]).json() if j["id"] == s["job"]["id"])
    loc = item["visit_location"]
    assert loc["has_home_pin"] and loc["checkin"]["away"] and 2100 < loc["checkin"]["distance_m"] < 2400
    assert loc["checkout"] is None


def test_near_check_in_no_alert(client, db, s):
    _pin(db, s["elder"])
    assert _status(client, s, "checked_in", NEAR, 10).status_code == 200
    assert _alerts(db) == []


def test_threshold_and_accuracy_allowance():
    limit = visit_location.AWAY_FROM_HOME_METERS
    assert not visit_location.is_away(limit, None)
    assert visit_location.is_away(limit + 1, None)
    assert not visit_location.is_away(limit + 50, 60)  # within GPS accuracy
    # The allowance is capped: a very rough fix cannot hide a real mismatch.
    assert visit_location.is_away(limit + visit_location.MAX_ACCURACY_ALLOWANCE_METERS + 1, 5000)
    assert visit_location.distance_label(2300) == "2.3 km"
    assert visit_location.distance_label(434) == "430 m"


def test_no_home_pin_records_but_no_alert(client, db, s):
    assert _status(client, s, "checked_in", FAR, 10).status_code == 200
    job = db.get(CareJob, s["job"]["id"])
    db.refresh(job)
    assert job.checkin_lat == FAR[0]
    assert _alerts(db) == []


def test_staff_location_optional_and_stored(client, db, s):
    _pin(db, s["elder"])
    jid = s["job"]["id"]
    # Office staff without a location are not blocked; nothing is stored.
    res = client.post(f"/api/v1/jobs/{jid}/progress", json={"status": "checked_in"}, headers=s["staff"])
    assert res.status_code == 200, res.text
    job = db.get(CareJob, jid)
    db.refresh(job)
    assert job.checkin_lat is None
    res = client.post(
        f"/api/v1/jobs/{jid}/report",
        json={**KUSHLIFE, "latitude": FAR[0], "longitude": FAR[1], "accuracy": 30},
        headers=s["staff"],
    )
    assert res.status_code == 200, res.text
    db.refresh(job)
    assert job.checkout_lat == FAR[0]
    assert {r.dedupe_key.rsplit(":", 1)[0] for r in _alerts(db)} == {f"visit_loc:{jid}:checkout"}


def test_log_past_visit_ignores_location(client, db, s):
    _pin(db, s["elder"])
    when = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    res = client.post(
        "/api/v1/jobs/log-past",
        json={"elder_id": s["elder"].id, "visited_at": when, **KUSHLIFE, "latitude": FAR[0], "longitude": FAR[1]},
        headers=s["staff"],
    )
    assert res.status_code == 201, res.text
    job = db.get(CareJob, res.json()["id"])
    # Logged from the office afterwards: no location kept, no false "away" alert.
    assert job.checkout_lat is None and _alerts(db) == []
