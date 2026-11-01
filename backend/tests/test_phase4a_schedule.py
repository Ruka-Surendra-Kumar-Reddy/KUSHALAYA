"""Phase 4A: repeating visits, weekly roster, leave and cover (FIX_TODO 93, 96)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import hash_password
from app.livewell import care_jobs
from app.livewell.care_series import HORIZON_DAYS, IST, ist_today, top_up_series
from app.models.care_job import CareJob
from app.models.care_series import CareSeries
from app.models.caregiver import Caregiver
from app.models.user import User

S = "/api/v1/schedule"


@pytest.fixture
def told(monkeypatch):
    sent: list[tuple[int, str, str]] = []
    monkeypatch.setattr(
        care_jobs, "_notify_family", lambda db, elder, title, body, event="visit": sent.append((elder.id, title, body))
    )
    return sent


def _monday(weeks_ahead: int = 1):
    today = ist_today()
    return today + timedelta(days=7 - today.weekday() + 7 * (weeks_ahead - 1))


def _series(client, headers, elder_id, cg_id, **extra):
    body = {
        "elder_id": elder_id,
        "caregiver_id": cg_id,
        "weekdays": [0, 2, 4],
        "time": "10:00",
        "duration_minutes": 60,
        "start_date": _monday().isoformat(),
        **extra,
    }
    res = client.post(f"{S}/series", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _jobs(db, series_id):
    db.expire_all()
    return db.query(CareJob).filter(CareJob.series_id == series_id).order_by(CareJob.series_date).all()


def _live(db, series_id):
    return [j for j in _jobs(db, series_id) if j.status != "cancelled"]


def _aware(dt):
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _caregiver(db, tenant_id, manager_id, first):
    cg = Caregiver(tenant_id=tenant_id, first_name=first, last_name="Test", manager_user_id=manager_id)
    db.add(cg)
    db.commit()
    return cg


def test_series_generates_mwf_jobs_in_ist(client, db, seed_tenant, auth_headers, told):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    out = _series(client, auth_headers, elder.id, cg.id, weeks=2)
    assert out["created"] == 6 and out["clashes"] == []
    assert out["series"]["days_label"] == "Mon/Wed/Fri"
    jobs = _jobs(db, out["series"]["id"])
    assert [j.series_date.weekday() for j in jobs] == [0, 2, 4, 0, 2, 4]
    for j in jobs:
        local = _aware(j.scheduled_at).astimezone(IST)
        assert (local.hour, local.minute) == (10, 0)
        assert local.date() == j.series_date
        assert _aware(j.scheduled_at).astimezone(timezone.utc).hour == 4  # 10:00 IST = 04:30 UTC, always
        assert j.caregiver_id == cg.id and j.status == "scheduled"
    assert out["series"]["end_date"] == (_monday() + timedelta(days=13)).isoformat()
    assert len(told) == 1 and "Mon/Wed/Fri" in told[0][2]  # one family notice, not six


def test_horizon_top_up_is_idempotent(client, db, seed_tenant, auth_headers, told):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    out = _series(client, auth_headers, elder.id, cg.id)  # open-ended
    sid = out["series"]["id"]
    first = len(_jobs(db, sid))
    assert first == out["created"] and first > 0
    assert max(j.series_date for j in _jobs(db, sid)) <= ist_today() + timedelta(days=HORIZON_DAYS)
    now = datetime.now(timezone.utc)
    assert sid not in top_up_series(db, now=now)
    later = now + timedelta(days=7)
    added = top_up_series(db, now=later)
    assert added.get(sid) == 3  # one more week of Mon/Wed/Fri
    assert sid not in top_up_series(db, now=later)
    keys = [(j.series_id, j.series_date) for j in _jobs(db, sid)]
    assert len(keys) == len(set(keys)) == first + 3


def test_edit_this_visit_only(client, db, seed_tenant, auth_headers, told):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    sid = _series(client, auth_headers, elder.id, cg.id, weeks=2)["series"]["id"]
    target = _jobs(db, sid)[1]
    res = client.post(
        f"{S}/series/{sid}/change", json={"job_id": target.id, "scope": "one", "time": "15:30"}, headers=auth_headers
    )
    assert res.status_code == 200, res.text
    jobs = _jobs(db, sid)
    times = [_aware(j.scheduled_at).astimezone(IST).strftime("%H:%M") for j in jobs]
    assert times == ["10:00", "15:30", "10:00", "10:00", "10:00", "10:00"]
    # Cancelling one visit only is not undone by the timer.
    client.patch(f"/api/v1/jobs/{jobs[2].id}", json={"status": "cancelled"}, headers=auth_headers)
    top_up_series(db)
    assert len(_jobs(db, sid)) == 6


def test_edit_this_and_following_splits_series(client, db, seed_tenant, auth_headers, told):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    sid = _series(client, auth_headers, elder.id, cg.id, weeks=2)["series"]["id"]
    third = _jobs(db, sid)[3]  # Monday of week 2
    res = client.post(
        f"{S}/series/{sid}/change",
        json={"job_id": third.id, "scope": "following", "weekdays": [1], "time": "09:00"},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    out = res.json()
    new_id = out["series"]["id"]
    assert out["previous_id"] == sid and out["removed"] == 3
    old = db.get(CareSeries, sid)
    assert old.end_date == third.series_date - timedelta(days=1)
    assert len(_live(db, sid)) == 3
    dropped = [j for j in _jobs(db, sid) if j.status == "cancelled"]
    assert len(dropped) == 3 and all(j.staff_note == "Series changed" for j in dropped)  # kept, not deleted
    new_jobs = _jobs(db, new_id)
    assert [j.series_date.weekday() for j in new_jobs] == [1]
    assert _aware(new_jobs[0].scheduled_at).astimezone(IST).strftime("%H:%M") == "09:00"
    assert told[-1][1] == "Regular visits changed"


def test_end_series_now(client, db, seed_tenant, auth_headers, told):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    sid = _series(client, auth_headers, elder.id, cg.id)["series"]["id"]
    res = client.post(f"{S}/series/{sid}/end", json={}, headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["series"]["status"] == "ended"
    assert _live(db, sid) == []
    top_up_series(db, now=datetime.now(timezone.utc) + timedelta(days=14))
    assert _live(db, sid) == []
    listed = client.get(f"{S}/series", headers=auth_headers).json()
    assert sid not in [s["id"] for s in listed]


def test_end_series_on_date_keeps_earlier_visits(client, db, seed_tenant, auth_headers, told):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    sid = _series(client, auth_headers, elder.id, cg.id, weeks=3)["series"]["id"]
    last = _monday() + timedelta(days=6)
    res = client.post(f"{S}/series/{sid}/end", json={"end_date": last.isoformat()}, headers=auth_headers)
    assert res.status_code == 200, res.text
    assert [j.series_date.weekday() for j in _live(db, sid)] == [0, 2, 4]


def test_clashes_are_reported_not_skipped(client, db, seed_tenant, auth_headers, told):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    wed = _monday() + timedelta(days=2)
    at = datetime(wed.year, wed.month, wed.day, 10, 30, tzinfo=IST)
    res = client.post(
        "/api/v1/jobs",
        json={"elder_id": elder.id, "kind": "visit", "scheduled_at": at.astimezone(timezone.utc).isoformat(), "caregiver_id": cg.id},
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    out = _series(client, auth_headers, elder.id, cg.id, weeks=1)
    assert out["created"] == 3
    assert len(out["clashes"]) == 1 and out["clashes"][0]["date"] == wed.isoformat()
    assert "already has a visit" in out["clashes"][0]["reason"]
    clash_job = db.get(CareJob, out["clashes"][0]["job_id"])
    assert clash_job.caregiver_id is None and clash_job.staff_note.startswith("Needs a caregiver")
    assert out["series"]["clashes"][0]["job_id"] == clash_job.id


def _leave_setup(client, db, seed_tenant, auth_headers):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    out = _series(client, auth_headers, elder.id, cg.id, weeks=2)
    mon = _monday()
    res = client.post(
        f"{S}/leave",
        json={"caregiver_id": cg.id, "leave_type": "SICK", "start_date": mon.isoformat(),
              "end_date": (mon + timedelta(days=2)).isoformat()},
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    return out["series"]["id"], res.json()["leave"]


def test_leave_approval_lists_affected_visits(client, db, seed_tenant, auth_headers, told):
    _, leave = _leave_setup(client, db, seed_tenant, auth_headers)
    assert leave["status"] == "PENDING" and leave["affected_count"] == 2
    res = client.post(f"{S}/leave/{leave['id']}/approve", headers=auth_headers)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["leave"]["status"] == "APPROVED"
    days = sorted(a["scheduled_at"][:10] for a in out["affected"])
    assert len(days) == 2  # Mon and Wed fall in the leave; Fri does not
    listed = client.get(f"{S}/leave", headers=auth_headers).json()
    assert listed[0]["id"] == leave["id"]
    # Roster marks the leave days.
    roster = client.get(f"{S}/roster", params={"week": _monday().isoformat()}, headers=auth_headers).json()
    row = next(r for r in roster["caregivers"] if r["caregiver_id"] == seed_tenant["caregiver"].id)
    assert row["days"][0]["leave"]["status"] == "APPROVED" and row["days"][4]["leave"] is None
    assert len(row["days"][0]["visits"]) == 1 and len(row["days"][1]["visits"]) == 0


def test_cover_suggestions_exclude_clashes_and_same_team_first(client, db, seed_tenant, auth_headers, told):
    sid, leave = _leave_setup(client, db, seed_tenant, auth_headers)
    client.post(f"{S}/leave/{leave['id']}/approve", headers=auth_headers)
    tenant_id, mgr = seed_tenant["tenant"].id, seed_tenant["manager"].id
    free = _caregiver(db, tenant_id, mgr, "Free")
    busy = _caregiver(db, tenant_id, mgr, "Busy")
    job = _jobs(db, sid)[0]
    db.add(CareJob(tenant_id=tenant_id, elder_id=job.elder_id, kind="visit", scheduled_at=job.scheduled_at,
                   duration_minutes=30, caregiver_id=busy.id, status="scheduled"))
    db.commit()
    res = client.get(f"{S}/cover/{job.id}", headers=auth_headers)
    assert res.status_code == 200, res.text
    ids = [s["caregiver_id"] for s in res.json()["suggestions"]]
    assert free.id in ids and busy.id not in ids and seed_tenant["caregiver"].id not in ids
    assert res.json()["suggestions"][0]["same_team"] is True
    assert res.json()["busy_count"] >= 1


def test_bulk_reassign_reports_clashes_and_tells_family(client, db, seed_tenant, auth_headers, told):
    sid, leave = _leave_setup(client, db, seed_tenant, auth_headers)
    affected = client.post(f"{S}/leave/{leave['id']}/approve", headers=auth_headers).json()["affected"]
    tenant_id, mgr = seed_tenant["tenant"].id, seed_tenant["manager"].id
    free = _caregiver(db, tenant_id, mgr, "Free")
    busy = _caregiver(db, tenant_id, mgr, "Busy")
    first = db.get(CareJob, affected[0]["id"])
    db.add(CareJob(tenant_id=tenant_id, elder_id=first.elder_id, kind="visit", scheduled_at=first.scheduled_at,
                   duration_minutes=30, caregiver_id=busy.id, status="scheduled"))
    db.commit()
    ids = [a["id"] for a in affected]
    res = client.post(f"{S}/reassign", json={"job_ids": ids, "caregiver_id": busy.id}, headers=auth_headers)
    out = res.json()
    assert [f["job_id"] for f in out["failed"]] == [ids[0]] and len(out["moved"]) == 1
    told.clear()
    res = client.post(f"{S}/reassign", json={"job_ids": [ids[0]], "caregiver_id": free.id}, headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["moved"][0]["caregiver_id"] == free.id
    assert told and told[0][1] == "Change of caregiver" and "Free will visit instead of Care" in told[0][2]


def test_team_scope(client, db, seed_tenant, auth_headers, told):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    sid = _series(client, auth_headers, elder.id, cg.id, weeks=1)["series"]["id"]
    other = User(email="other.mgr@test.example", password_hash=hash_password("testpass123"), first_name="Other",
                 last_name="Mgr", role="CARE_MANAGER", tenant_id=seed_tenant["tenant"].id)
    db.add(other)
    db.commit()
    res = client.post("/api/v1/auth/login", json={"email": other.email, "password": "testpass123"})
    h = {"Authorization": f"Bearer {res.json()['access_token']}"}
    assert client.get(f"{S}/series", headers=h).json() == []
    assert client.post(f"{S}/series/{sid}/end", json={}, headers=h).status_code == 404
    roster = client.get(f"{S}/roster", params={"week": _monday().isoformat()}, headers=h).json()
    assert roster["caregivers"] == [] and roster["unassigned"] is None
    mine = client.get(f"{S}/roster", params={"week": _monday().isoformat()}, headers=auth_headers).json()
    row = next(r for r in mine["caregivers"] if r["caregiver_id"] == cg.id)
    assert [len(d["visits"]) for d in row["days"]] == [1, 0, 1, 0, 1, 0, 0]
    res = client.post(
        f"{S}/leave",
        json={"caregiver_id": cg.id, "start_date": _monday().isoformat(), "end_date": _monday().isoformat()},
        headers=h,
    )
    assert res.status_code == 404
    assert client.post(f"{S}/series", json={"elder_id": elder.id, "weekdays": [0], "time": "10:00"},
                       headers=h).status_code == 404


# --- Phase 4 audit fixes -----------------------------------------------------------


def test_inactive_caregiver_is_a_clash_and_rejected(client, db, seed_tenant, auth_headers, told):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    sid = _series(client, auth_headers, elder.id, cg.id, weeks=2)["series"]["id"]
    cg.status = "INACTIVE"
    db.commit()
    # New assignment is refused in plain words.
    res = client.post(f"{S}/series", json={"elder_id": elder.id, "caregiver_id": cg.id, "weekdays": [1],
                                           "time": "10:00", "start_date": _monday().isoformat()}, headers=auth_headers)
    assert res.status_code == 400 and "no longer works with us" in res.text
    when = datetime.combine(_monday(), datetime.min.time(), tzinfo=IST) + timedelta(hours=15)
    res = client.post("/api/v1/jobs", json={"elder_id": elder.id, "kind": "visit", "caregiver_id": cg.id,
                                            "scheduled_at": when.isoformat()}, headers=auth_headers)
    assert res.status_code == 400 and "no longer works with us" in res.text
    # Splitting a series that keeps the leaver: each day is created unassigned and reported.
    third = _jobs(db, sid)[3]
    res = client.post(f"{S}/series/{sid}/change", json={"job_id": third.id, "scope": "following", "time": "11:00"},
                      headers=auth_headers)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["created"] == 3 and len(out["clashes"]) == 3
    assert all("no longer works with us" in c["reason"] for c in out["clashes"])
    assert all(j.caregiver_id is None for j in _jobs(db, out["series"]["id"]))


def test_series_change_cancels_old_visits_and_recreates_days(client, db, seed_tenant, auth_headers, told):
    from app.livewell.daily_checks import mark_missed_visits
    from app.models.audit_log import AuditLog

    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    sid = _series(client, auth_headers, elder.id, cg.id, weeks=2)["series"]["id"]
    third = _jobs(db, sid)[3]
    res = client.post(f"{S}/series/{sid}/change", json={"job_id": third.id, "scope": "following", "time": "11:00"},
                      headers=auth_headers)
    assert res.status_code == 200, res.text
    new_id = res.json()["series"]["id"]
    # Same days as before: the cancelled visits of the old series do not block them.
    assert [j.series_date for j in _jobs(db, new_id)] == [j.series_date for j in _jobs(db, sid)[3:]]
    cancelled = [j for j in _jobs(db, sid) if j.status == "cancelled"]
    assert len(cancelled) == 3
    logs = db.query(AuditLog).filter(AuditLog.action == "series_visit_cancelled").all()
    assert {l.entity_id for l in logs} == {j.id for j in cancelled}
    # Never marked missed, and not in the staff job list.
    gone = {j.id for j in cancelled}
    assert not set(mark_missed_visits(db, now=datetime.now(timezone.utc) + timedelta(days=40))) & gone
    listed = {j["id"] for j in client.get("/api/v1/jobs", params={"elder_id": elder.id}, headers=auth_headers).json()}
    assert not listed & gone


def test_roster_shows_other_team_caregiver_in_own_row(client, db, seed_tenant, auth_headers, told):
    elder = seed_tenant["elder"]
    outsider = _caregiver(db, seed_tenant["tenant"].id, seed_tenant["admin"].id, "Outside")
    at = datetime.combine(_monday(), datetime.min.time(), tzinfo=IST) + timedelta(hours=9)
    db.add(CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, kind="visit", title="Cover", scheduled_at=at,
                   duration_minutes=60, caregiver_id=outsider.id, status="scheduled"))
    db.commit()
    roster = client.get(f"{S}/roster", params={"week": _monday().isoformat()}, headers=auth_headers).json()
    row = next(r for r in roster["caregivers"] if r["caregiver_id"] == outsider.id)
    assert row["name"] == "Other team: Outside Test" and row["other_team"] is True
    assert len(row["days"][0]["visits"]) == 1
    assert roster["unassigned"] is None


def test_top_up_carries_on_past_a_bad_series(client, db, seed_tenant, auth_headers, told, monkeypatch):
    from app.livewell import care_series

    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    bad = _series(client, auth_headers, elder.id, cg.id)["series"]["id"]
    good = _series(client, auth_headers, elder.id, None, weekdays=[1])["series"]["id"]
    real = care_series.generate

    def flaky(db_, series, *, now=None):
        if series.id == bad:
            raise RuntimeError("boom")
        return real(db_, series, now=now)

    monkeypatch.setattr(care_series, "generate", flaky)
    added = top_up_series(db, now=datetime.now(timezone.utc) + timedelta(days=7))
    assert added.get(good) == 1 and bad not in added


def test_following_keeps_a_one_off_edit(client, db, seed_tenant, auth_headers, told):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    sid = _series(client, auth_headers, elder.id, cg.id, weeks=2)["series"]["id"]
    third = _jobs(db, sid)[3]
    res = client.post(f"{S}/series/{sid}/change", json={"job_id": third.id, "scope": "one", "time": "15:30"},
                      headers=auth_headers)
    assert res.status_code == 200, res.text
    res = client.post(f"{S}/series/{sid}/change",
                      json={"job_id": third.id, "scope": "following", "time": "08:00"}, headers=auth_headers)
    assert res.status_code == 200, res.text
    out = res.json()
    assert [k["id"] for k in out["kept"]] == [third.id] and out["removed"] == 2
    db.expire_all()
    kept = db.get(CareJob, third.id)
    assert kept.status == "scheduled" and _aware(kept.scheduled_at).astimezone(IST).strftime("%H:%M") == "15:30"
    new_jobs = _jobs(db, out["series"]["id"])
    assert [j.series_date for j in new_jobs].count(third.series_date) == 1  # not doubled
    # An unedited split day is replaced as before.
    sid2 = out["series"]["id"]
    nxt = _jobs(db, sid2)[1]
    out2 = client.post(f"{S}/series/{sid2}/change", json={"job_id": nxt.id, "scope": "following", "time": "09:00"},
                       headers=auth_headers).json()
    assert out2["kept"] == []


def test_assigning_clears_needs_a_caregiver_note(client, db, seed_tenant, auth_headers, told):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    wed = _monday() + timedelta(days=2)
    at = datetime(wed.year, wed.month, wed.day, 10, 30, tzinfo=IST)
    client.post("/api/v1/jobs", json={"elder_id": elder.id, "kind": "visit", "caregiver_id": cg.id,
                                      "scheduled_at": at.isoformat()}, headers=auth_headers)
    out = _series(client, auth_headers, elder.id, cg.id, weeks=1)
    job_id = out["clashes"][0]["job_id"]
    free = _caregiver(db, seed_tenant["tenant"].id, seed_tenant["manager"].id, "Free")
    res = client.patch(f"/api/v1/jobs/{job_id}", json={"caregiver_id": free.id}, headers=auth_headers)
    assert res.status_code == 200, res.text
    db.expire_all()
    assert db.get(CareJob, job_id).staff_note == ""


def test_job_time_with_offset_is_stored_as_utc(client, db, seed_tenant, auth_headers, told):
    elder, cg = seed_tenant["elder"], seed_tenant["caregiver"]
    day = _monday() + timedelta(days=1)
    res = client.post("/api/v1/jobs", json={"elder_id": elder.id, "kind": "visit", "caregiver_id": cg.id,
                                            "scheduled_at": f"{day.isoformat()}T10:00:00+05:30"}, headers=auth_headers)
    assert res.status_code == 201, res.text
    db.expire_all()
    job = db.get(CareJob, res.json()["id"])
    assert _aware(job.scheduled_at) == datetime(day.year, day.month, day.day, 4, 30, tzinfo=timezone.utc)
    res = client.patch(f"/api/v1/jobs/{job.id}", json={"scheduled_at": f"{day.isoformat()}T16:00:00+05:30"},
                       headers=auth_headers)
    assert res.status_code == 200, res.text
    db.expire_all()
    stored = _aware(db.get(CareJob, job.id).scheduled_at)
    assert stored == datetime(day.year, day.month, day.day, 10, 30, tzinfo=timezone.utc)
