"""Phase 1B: dashboard reassessments / missed / approvals / alert scoping, and staff inbox unread."""

from datetime import datetime, timedelta, timezone

from app.models.care_job import CareJob
from app.models.commerce import Order
from app.models.elder import Elder
from app.models.incident import Incident

URL = "/api/v1/home-safety/dashboard/attention"


def _login(client, email):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_reassessments_and_viewer_in_attention(client, seed_tenant, auth_headers):
    body = client.get(URL, headers=auth_headers).json()
    elder = seed_tenant["elder"]
    row = next(r for r in body["reassessments"] if r["elder_id"] == elder.id)
    assert row["needs_first"] is True
    assert body["counts"]["reassessments"] == len(body["reassessments"])
    assert body["viewer"]["first_name"] == "Test"
    assert body["viewer"]["is_admin"] is False


def test_missed_group_lists_past_unfinished_jobs(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    now = datetime.now(timezone.utc)
    db.add_all(
        [
            CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, kind="visit", title="Missed", created_at=now - timedelta(days=9),
                    scheduled_at=now - timedelta(days=2), status="missed"),
            CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, kind="visit", title="Never started", created_at=now - timedelta(days=10),
                    scheduled_at=now - timedelta(days=3), status="scheduled"),
            CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, kind="visit", title="Done", created_at=now - timedelta(days=9),
                    scheduled_at=now - timedelta(days=2), status="completed"),
            CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, kind="visit", title="Too old", created_at=now - timedelta(days=19),
                    scheduled_at=now - timedelta(days=12), status="missed"),
        ]
    )
    db.commit()
    body = client.get(URL, headers=auth_headers).json()
    assert sorted(m["title"] for m in body["missed"]) == ["Missed", "Never started"]
    assert body["counts"]["missed"] == 2


def test_approvals_only_for_admins(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    db.add(Order(tenant_id=elder.tenant_id, elder_id=elder.id, status="pending_approval",
                 subtotal_paise=800000, discount_paise=120000, total_paise=680000))
    db.commit()
    assert client.get(URL, headers=auth_headers).json()["approvals"] == []
    admin = client.get(URL, headers=_login(client, "admin@test.example")).json()
    assert len(admin["approvals"]) == 1
    assert admin["viewer"]["is_admin"] is True


def test_alerts_team_filter_before_limit(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    other = Elder(tenant_id=elder.tenant_id, first_name="Other", last_name="Team", status="ACTIVE")
    db.add(other)
    db.flush()
    now = datetime.now(timezone.utc)
    db.add(Incident(tenant_id=elder.tenant_id, elder_id=elder.id, kind="fall", severity="critical",
                    status="open", opened_at=now - timedelta(hours=2)))
    # 60 newer alerts for a client outside the manager's team.
    db.add_all(
        Incident(tenant_id=elder.tenant_id, elder_id=other.id, kind="battery_low", severity="info",
                 status="open", opened_at=now - timedelta(minutes=i))
        for i in range(60)
    )
    db.commit()
    alerts = client.get(URL, headers=auth_headers).json()["alerts"]
    assert [a["elder_id"] for a in alerts] == [elder.id]
    assert alerts[0]["kind"] == "fall"


def test_mark_unread_and_unread_first(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    second = Elder(tenant_id=elder.tenant_id, first_name="Second", last_name="Client", status="ACTIVE",
                   manager_user_id=seed_tenant["manager"].id)
    db.add(second)
    db.flush()
    t0 = datetime.now(timezone.utc) - timedelta(hours=1)
    elder.custom_attributes = {
        **(elder.custom_attributes or {}),
        "safe_home": {"family_hub": {"messages": [{"id": "m1", "body": "Hi", "sender_role": "family",
                                                   "created_at": t0.isoformat()}]}},
    }
    second.custom_attributes = {
        "safe_home": {"family_hub": {"messages": [{"id": "m2", "body": "Newer", "sender_role": "family",
                                                   "created_at": (t0 + timedelta(minutes=30)).isoformat()}]}},
    }
    db.commit()
    base = "/api/v1/home-safety/care/family-messages"
    # Read the newer thread: the older unread one now comes first.
    assert client.post(f"{base}/{second.id}/read", headers=auth_headers).status_code == 200
    rows = client.get(base, headers=auth_headers).json()
    assert [r["elder_id"] for r in rows][:2] == [elder.id, second.id]

    res = client.post(f"{base}/{second.id}/unread", headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["unread_count"] == 1
    rows = client.get(base, headers=auth_headers).json()
    assert [r["elder_id"] for r in rows][:2] == [second.id, elder.id]

    ctx = client.get(f"{base}/{second.id}/context", headers=auth_headers).json()
    assert ctx["manager_name"] == "Test Manager"
    assert ctx["open_alerts"] == 0


def test_mark_unread_with_naive_dates_and_viewer_blocked(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    naive = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None).isoformat()
    aware = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    elder.custom_attributes = {
        **(elder.custom_attributes or {}),
        "safe_home": {"family_hub": {"messages": [
            {"id": "n1", "body": "Old", "sender_role": "family", "created_at": naive},
            {"id": "n2", "body": "New", "sender_role": "family", "created_at": aware},
        ]}},
    }
    db.commit()
    base = "/api/v1/home-safety/care/family-messages"
    res = client.post(f"{base}/{elder.id}/unread", headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["unread_count"] == 1

    viewer = _login(client, "viewer@test.example")
    assert client.post(f"{base}/{elder.id}/unread", headers=viewer).status_code == 403
    assert client.post(f"{base}/{elder.id}/read", headers=viewer).status_code == 403


def test_rebooked_missed_job_is_hidden(client, db, seed_tenant, auth_headers):
    elder = seed_tenant["elder"]
    now = datetime.now(timezone.utc)
    db.add_all(
        [
            CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, kind="visit", title="Missed",
                    scheduled_at=now - timedelta(days=2), status="missed"),
            CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, kind="visit", title="Rebooked",
                    scheduled_at=now + timedelta(days=1), status="scheduled"),
        ]
    )
    db.commit()
    assert client.get(URL, headers=auth_headers).json()["missed"] == []
