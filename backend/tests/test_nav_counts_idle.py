"""Sidebar badge counts (team scoped) and sign-out after inactivity (sliding refresh tokens)."""

import time
from datetime import datetime, timedelta, timezone

from app.core.security import create_refresh_token, decode_token, hash_password
from app.core.session_policy import refresh_rejection
from app.models.care_job import CareJob
from app.models.elder import Elder
from app.models.incident import Incident
from app.models.user import User
from app.services.auth_service import _bind_to_user

URL = "/api/v1/dashboard/nav-counts"


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()


def _headers(body):
    return {"Authorization": f"Bearer {body['access_token']}"}


def _seed_counts(db, seed_tenant):
    elder = seed_tenant["elder"]
    now = datetime.now(timezone.utc)
    elder.custom_attributes = {
        **(elder.custom_attributes or {}),
        "safe_home": {"service_requests": [{"id": "r1", "service_type": "nurse_pt", "status": "requested", "created_at": now.isoformat()}]},
    }
    other = Elder(
        tenant_id=elder.tenant_id,
        first_name="Other",
        last_name="Team",
        status="ACTIVE",
        custom_attributes={"safe_home": {"service_requests": [{"id": "x", "status": "requested"}]}},
    )
    db.add(other)
    db.flush()
    db.add(Incident(tenant_id=elder.tenant_id, elder_id=elder.id, kind="fall", severity="critical", status="open", opened_at=now))
    db.add_all(
        Incident(tenant_id=elder.tenant_id, elder_id=other.id, kind="battery_low", severity="info", status="open", opened_at=now)
        for _ in range(3)
    )
    db.add(Incident(tenant_id=elder.tenant_id, elder_id=elder.id, kind="fall", severity="critical", status="resolved", opened_at=now))
    db.add(CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, kind="care_visit", title="Visit",
                   scheduled_at=(now - timedelta(days=2)).replace(tzinfo=None), status="missed"))
    db.commit()
    return elder, other


def test_nav_counts_are_team_scoped(client, db, seed_tenant):
    _seed_counts(db, seed_tenant)
    mine = client.get(URL, headers=_headers(_login(client, "manager@test.example")))
    assert mine.status_code == 200, mine.text
    m = mine.json()
    assert m["alerts"] == 1  # other team's 3 and the resolved one don't count
    due = m["requests"] - 1  # (re)assessments waiting to be booked count as requests too
    assert due >= 0
    assert m["missed"] == 1
    assert m["approvals"] == 0
    assert m["nav"]["dashboard"] == 1
    assert m["nav"]["schedule"] == 2 + due
    assert all(isinstance(v, int) for k, v in m.items() if k != "nav")

    admin = client.get(URL, headers=_headers(_login(client, "admin@test.example"))).json()
    assert admin["alerts"] == 4
    assert admin["requests"] >= 2


def test_visits_badge_matches_requests_tab(client, db, seed_tenant):
    """The Visits menu badge counts exactly what the Requests tab lists (requests + due assessments)."""
    _seed_counts(db, seed_tenant)
    for email in ("manager@test.example", "admin@test.example"):
        h = _headers(_login(client, email))
        counts = client.get(URL, headers=h).json()
        attn = client.get("/api/v1/home-safety/dashboard/attention", headers=h)
        assert attn.status_code == 200, attn.text
        a = attn.json()
        assert counts["requests"] == len(a["requests"]) + len(a.get("reassessments") or [])
        assert counts["nav"]["schedule"] == counts["requests"] + counts["missed"]


def test_nav_counts_needs_login(client, seed_tenant):
    assert client.get(URL).status_code in (401, 403)


def test_login_refresh_token_carries_session_times(client, seed_tenant):
    body = _login(client, "manager@test.example")
    assert body["idle_minutes"] is None  # no sign-out for inactivity
    payload = decode_token(body["refresh_token"])
    assert payload["auth_time"] and payload["lst"]

    res = client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert res.status_code == 200, res.text
    fresh = decode_token(res.json()["refresh_token"])
    assert fresh["auth_time"] == payload["auth_time"]  # sign-in time is kept
    assert res.json()["idle_minutes"] is None


def _token(user, **claims):
    return _bind_to_user(create_refresh_token(user.email), user, claims)


def test_idle_refresh_token_is_not_rejected(client, seed_tenant):
    manager = seed_tenant["manager"]
    now = time.time()
    stale = _token(manager, auth_time=int(now - 3 * 3600), lst=int(now - 2 * 3600))
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": stale})
    assert res.status_code == 200, res.text


def test_no_staff_absolute_limit(client, seed_tenant):
    now = time.time()
    old = _token(seed_tenant["manager"], auth_time=int(now - 30 * 3600), lst=int(now - 60))
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": old}).status_code == 200


def test_legacy_refresh_token_still_works(client, seed_tenant):
    legacy = _bind_to_user(create_refresh_token("manager@test.example"), seed_tenant["manager"])
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": legacy})
    assert res.status_code == 200, res.text
    assert decode_token(res.json()["refresh_token"])["lst"]


def test_garbage_refresh_token_is_still_refused(client, seed_tenant):
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-token"}).status_code in (400, 401)


def test_old_saved_idle_setting_is_ignored(client, db, seed_tenant):
    tenant = seed_tenant["tenant"]
    tenant.workflow_config = {**(tenant.workflow_config or {}), "security": {"staff_idle_minutes": 5}}
    db.commit()
    body = _login(client, "manager@test.example")
    assert body["idle_minutes"] is None
    now = time.time()
    tok = _token(seed_tenant["manager"], auth_time=int(now - 3600), lst=int(now - 3000))
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tok}).status_code == 200
    headers = _headers(body)
    assert client.get("/api/v1/team/security-settings", headers=headers).json() == {"idle_timeout": False}


def test_refresh_rejection_never_refuses():
    now = 1_000_000.0
    policy = {"idle_minutes": None, "absolute_hours": 0}
    assert refresh_rejection({}, policy, 60, now=now) is None
    assert refresh_rejection({"lst": now - 30 * 86400, "auth_time": now - 60 * 86400}, policy, 60, now=now) is None
