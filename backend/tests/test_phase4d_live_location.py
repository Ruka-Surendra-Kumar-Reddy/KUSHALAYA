"""Phase 4D (#115): live "on the way" location — caregiver sends, family and ops see."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import hash_password
from app.livewell import live_location
from app.models.care_job import CareJob
from app.models.care_job_live_location import CareJobLiveLocation
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.elder_location import ElderLocation
from app.models.user import User

HOME = (17.4400, 78.3489)  # Gachibowli
NEAR = (17.4400, 78.3950)  # ~4.9 km east


def _login(client, email):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _user(db, email, role, tenant_id, **links):
    db.add(
        User(
            email=email,
            password_hash=hash_password("testpass123"),
            first_name="T",
            last_name="U",
            role=role,
            tenant_id=tenant_id,
            **links,
        )
    )
    db.commit()


@pytest.fixture
def setup(client, db, seed_tenant, auth_headers):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    db.add(ElderLocation(tenant_id=elder.tenant_id, elder_id=elder.id, latitude=HOME[0], longitude=HOME[1]))
    db.commit()
    when = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    job = client.post(
        "/api/v1/jobs",
        json={"elder_id": elder.id, "kind": "visit", "scheduled_at": when, "caregiver_id": cg.id},
        headers=auth_headers,
    ).json()
    _user(db, "live.cg@test.example", "CAREGIVER", cg.tenant_id, caregiver_id=cg.id)
    _user(db, "live.fam@test.example", "ELDER_PORTAL", elder.tenant_id, elder_id=elder.id)
    return {
        "job": job,
        "cg": _login(client, "live.cg@test.example"),
        "fam": _login(client, "live.fam@test.example"),
        "staff": auth_headers,
    }


def _status(client, s, step):
    res = client.post(f"/api/v1/caregiver-portal/jobs/{s['job']['id']}/status", json={"latitude": 17.4, "longitude": 78.4, "status": step}, headers=s["cg"])
    assert res.status_code == 200, res.text


def _send(client, s, lat=NEAR[0], lng=NEAR[1], headers=None, job_id=None):
    return client.post(
        f"/api/v1/caregiver-portal/jobs/{job_id or s['job']['id']}/location",
        json={"latitude": lat, "longitude": lng, "accuracy": 12},
        headers=headers or s["cg"],
    )


def test_eta_math():
    km = live_location.haversine_km(*HOME, *NEAR)
    assert 4.8 < km < 5.0
    assert live_location.eta_minutes(km) == 12  # 4.9 km at 25 km/h ≈ 11.8 → 12
    assert live_location.eta_label(km) == "about 12 min"
    assert live_location.eta_label(0.05) == "almost there"
    assert live_location.eta_minutes(0.01) == 1


def test_only_while_on_the_way(client, db, setup):
    s = setup
    assert _send(client, s).status_code == 400  # still scheduled
    _status(client, s, "on_the_way")
    res = _send(client, s)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["tracking"] is True and body["eta_label"] == "about 12 min" and body["stale"] is False
    # Only the latest point is kept.
    _send(client, s, lat=17.4401)
    assert db.query(CareJobLiveLocation).count() == 1
    assert _send(client, s, lat=95).status_code in (400, 422)


def test_only_own_job(client, db, seed_tenant, setup):
    s = setup
    _status(client, s, "on_the_way")
    other = Caregiver(tenant_id=seed_tenant["tenant"].id, first_name="Other", last_name="Cg", status="ACTIVE")
    db.add(other)
    db.commit()
    _user(db, "other.cg@test.example", "CAREGIVER", other.tenant_id, caregiver_id=other.id)
    res = _send(client, s, headers=_login(client, "other.cg@test.example"))
    assert res.status_code == 404
    # Family and staff cannot post through the caregiver route.
    assert _send(client, s, headers=s["fam"]).status_code == 403
    assert db.query(CareJobLiveLocation).count() == 0


def test_family_sees_while_on_the_way_then_arrived_without_map(client, db, setup):
    s = setup
    assert client.get("/api/v1/home-safety/family/live-visit", headers=s["fam"]).json() == {"live": None}
    _status(client, s, "on_the_way")
    _send(client, s)
    live = client.get("/api/v1/home-safety/family/live-visit", headers=s["fam"]).json()["live"]
    assert live["state"] == "on_the_way" and live["position"]["lat"] == NEAR[0]
    assert live["eta_label"] == "about 12 min" and live["home"]["lat"] == HOME[0]

    _status(client, s, "checked_in")
    assert db.query(CareJobLiveLocation).count() == 0  # cleared on arrival
    live = client.get("/api/v1/home-safety/family/live-visit", headers=s["fam"]).json()["live"]
    assert live["state"] == "arrived" and live["arrived_label"].startswith("Arrived at")
    assert "position" not in live and "home" not in live
    # Late update after arrival: told to stop, nothing stored.
    res = _send(client, s)
    assert res.status_code == 200 and res.json()["tracking"] is False
    assert db.query(CareJobLiveLocation).count() == 0

    _status(client, s, "completed")
    assert _send(client, s).status_code == 400
    assert client.get("/api/v1/home-safety/family/live-visit", headers=s["fam"]).json() == {"live": None}


def test_family_of_other_parent_sees_nothing(client, db, seed_tenant, setup):
    s = setup
    _status(client, s, "on_the_way")
    _send(client, s)
    other = Elder(tenant_id=seed_tenant["tenant"].id, first_name="Other", last_name="Parent", status="ACTIVE")
    db.add(other)
    db.commit()
    _user(db, "other.fam@test.example", "ELDER_PORTAL", other.tenant_id, elder_id=other.id)
    res = client.get("/api/v1/home-safety/family/live-visit", headers=_login(client, "other.fam@test.example"))
    assert res.json() == {"live": None}
    # Family schedule never carries the position either.
    assert str(NEAR[1]) not in client.get("/api/v1/home-safety/family/schedule", headers=s["fam"]).text


def test_stale_after_three_minutes(client, db, setup):
    s = setup
    _status(client, s, "on_the_way")
    _send(client, s)
    row = db.query(CareJobLiveLocation).one()
    row.updated_at = datetime.now(timezone.utc) - timedelta(minutes=4)
    db.commit()
    live = client.get("/api/v1/home-safety/family/live-visit", headers=s["fam"]).json()["live"]
    assert live["stale"] is True and live["position"] is not None


def test_cleared_when_staff_cancel_or_reassign(client, db, setup):
    s = setup
    _status(client, s, "on_the_way")
    _send(client, s)
    res = client.patch(f"/api/v1/jobs/{s['job']['id']}", json={"status": "cancelled"}, headers=s["staff"])
    assert res.status_code == 200, res.text
    assert db.query(CareJobLiveLocation).count() == 0


def test_ops_list_shows_live_in_team_only(client, db, seed_tenant, setup):
    s = setup
    _status(client, s, "on_the_way")
    _send(client, s)
    rows = client.get("/api/v1/jobs?open_only=true", headers=s["staff"]).json()
    mine = next(r for r in rows if r["id"] == s["job"]["id"])
    assert mine["live"]["eta_label"] == "about 12 min"

    # A job for a client outside the manager's team is not listed (nor its position).
    outside = Elder(tenant_id=seed_tenant["tenant"].id, first_name="Out", last_name="Side", status="ACTIVE")
    db.add(outside)
    db.commit()
    job = CareJob(tenant_id=outside.tenant_id, elder_id=outside.id, title="Visit", status="on_the_way",
                  scheduled_at=datetime.now(timezone.utc))
    db.add(job)
    db.commit()
    db.add(CareJobLiveLocation(job_id=job.id, tenant_id=job.tenant_id, latitude=17.5, longitude=78.5,
                               updated_at=datetime.now(timezone.utc)))
    db.commit()
    rows = client.get("/api/v1/jobs?open_only=true", headers=s["staff"]).json()
    assert job.id not in [r["id"] for r in rows]
    # Caregiver's own job list never carries the live block.
    assert all("live" not in j for j in client.get("/api/v1/caregiver-portal/jobs", headers=s["cg"]).json())


# --- Care manager sharing from the web, and the no-login tracking link ----------------


def _staff_send(client, s, lat=NEAR[0], lng=NEAR[1]):
    return client.post(
        f"/api/v1/jobs/{s['job']['id']}/location",
        json={"latitude": lat, "longitude": lng, "accuracy": 20},
        headers=s["staff"],
    )


def test_care_manager_shares_from_web_and_link_tracks_then_ends(client, db, setup):
    s = setup
    assert _staff_send(client, s).status_code == 400  # not on the way yet
    res = client.post(f"/api/v1/jobs/{s['job']['id']}/progress", json={"status": "on_the_way"}, headers=s["staff"])
    assert res.status_code == 200, res.text
    res = _staff_send(client, s)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["tracking"] is True and body["eta_label"] == "about 12 min"
    row = db.query(CareJobLiveLocation).one()
    assert row.shared_by_user_id is not None  # a staff member is sharing

    path = body["track_path"]
    assert path.startswith("/track/")
    token = path.split("/track/")[1]
    pub = client.get(f"/api/v1/home-safety/track/{token}")  # no login
    assert pub.status_code == 200, pub.text
    data = pub.json()
    assert data["state"] == "on_the_way" and data["position"]["lat"] == NEAR[0]
    assert data["eta_label"] == "about 12 min"
    # The home point for the route on the map — never the address text.
    assert data["home"]["lat"] == HOME[0] and "destination" not in data

    # Tampered or made-up links show nothing.
    assert client.get(f"/api/v1/home-safety/track/{token[:-1]}x").status_code == 404
    assert client.get("/api/v1/home-safety/track/abc").status_code == 404

    res = client.post(f"/api/v1/jobs/{s['job']['id']}/progress", json={"status": "checked_in"}, headers=s["staff"])
    assert res.status_code == 200, res.text
    data = client.get(f"/api/v1/home-safety/track/{token}").json()
    assert data["state"] == "arrived" and "position" not in data
    assert _staff_send(client, s).json()["tracking"] is False


def test_new_trip_gets_new_link(client, db, setup):
    s = setup
    _status(client, s, "on_the_way")
    job = db.get(CareJob, s["job"]["id"])
    first = live_location.track_token(job)
    job.started_at = job.started_at + timedelta(minutes=5)  # a later trip
    db.commit()
    assert live_location.track_token(job) != first
    assert client.get(f"/api/v1/home-safety/track/{first}").status_code == 404


def test_family_on_the_way_notice_carries_tracking_link(client, db, setup, monkeypatch):
    sent = []
    from app.livewell import family_notify

    monkeypatch.setattr(family_notify, "notify_family", lambda db, elder, title, body, **kw: sent.append((title, body, kw)))
    _status(client, setup, "on_the_way")
    assert sent, "family should be told"
    title, body, kw = sent[-1]
    assert "on the way" in title and "/track/" in body and kw["path"].startswith("/track/")
