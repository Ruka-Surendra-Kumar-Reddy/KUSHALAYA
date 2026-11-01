"""KushLife K2: Monday card, weekly summary (manager approves), "Normal for" baseline."""

from datetime import datetime, time, timedelta

from app.core.security import hash_password
from app.livewell import email_notifications as en
from app.livewell import kushlife as kl
from app.livewell import kushlife_weekly as kw
from app.models.kushlife_weekly import KushLifeWeekly
from app.models.user import User


def _kl(vitals=None, **changed):
    checks = {k: {"status": "ok"} for k in kl.CHECKS}
    for k, chips in changed.items():
        checks[k] = {"status": "concern", "chips": chips}
    return {"checks": checks, "sleep": "well", "appetite": "usual", "vitals": vitals or {"spo2": 97}}


def _log(client, headers, elder_id, when, **kw_):
    res = client.post("/api/v1/jobs/log-past", headers=headers,
                      json={"elder_id": elder_id, "visited_at": when.isoformat(), "kushlife": _kl(**kw_)})
    assert res.status_code == 201, res.text


def _last_week_day(n: int, hour: int = 10) -> datetime:
    return datetime.combine(kw.last_week_start() + timedelta(days=n), time(hour, 0), tzinfo=kw.IST)


def _monday_8am() -> datetime:
    return datetime.combine(kw.this_monday(), time(8, 0), tzinfo=kw.IST)


def _family(client, db, elder):
    admin = client.post("/api/v1/auth/login", json={"email": "admin@test.example", "password": "testpass123"}).json()
    ah = {"Authorization": f"Bearer {admin['access_token']}"}
    r = client.post(f"/api/v1/team/clients/{elder.id}/family-logins", headers=ah,
                    json={"email": "wk.fam@family.example", "password": "familypass1"})
    assert r.status_code in (200, 201), r.text
    fam = client.post("/api/v1/auth/login", json={"email": "wk.fam@family.example", "password": "familypass1"}).json()
    return {"Authorization": f"Bearer {fam['access_token']}"}


# --- baseline ---------------------------------------------------------------------


def test_baseline_math_ignores_outliers_and_needs_three():
    assert kl.robust_median([130, 128, 132, 200, 131, 129]) == 130
    assert kl.robust_median([130, 131]) is None
    assert kl.usual_answer(["well", "poorly", "well", None], kl.CATEGORICAL["sleep"]) == "well"
    recs = [{"checks": {"settled": {"chips": ["low_mood"] if i < 3 else []}}, "sleep": "poorly",
             "appetite": "usual", "vitals": {"bp_sys": 140 + i, "bp_dia": 90, "spo2": 95}} for i in range(5)]
    b = kl.computed_baseline(recs)
    assert b["bp_sys"] == 142 and b["bp_dia"] == 90 and b["spo2"] == 95 and b["pulse"] is None
    assert b["sleep"] == "poorly" and b["mood"] == "low"


def test_baseline_override_and_flags_use_it(client, db, seed_tenant, auth_headers, monkeypatch):
    monkeypatch.setattr(en, "send", lambda *a, **k: None)
    elder = seed_tenant["elder"]
    url = f"/api/v1/home-safety/clients/{elder.id}/kushlife/baseline"
    for i in range(3):
        _log(client, auth_headers, elder.id, datetime.now(kw.IST) - timedelta(days=10 - i),
             vitals={"bp_sys": 130, "bp_dia": 85, "spo2": 90, "pulse": 72})
    base = client.get(url, headers=auth_headers).json()
    assert base["values"]["bp_sys"] == 130 and base["source"]["spo2"] == "visits"
    assert base["label"] == "Normal for Elder"

    # Oxygen 90% is red by the generic rule, but it is this client's normal: not red.
    rec = kl.build_record({"kushlife": _kl(vitals={"spo2": 90})})
    assert kl.visit_level(rec)[0] == "red"
    assert kl.visit_level(rec, base["values"])[0] == "ok"
    # BP 160/85 vs a normal of 130/85 → amber, with the normal in the reason.
    rec = kl.build_record({"kushlife": _kl(vitals={"bp_sys": 160, "bp_dia": 85})})
    level, reasons = kl.visit_level(rec, base["values"])
    assert level == "amber" and any("usually 130/85" in r for r in reasons)

    # Staff override wins; a bad value is refused; null clears it.
    r = client.put(url, headers=auth_headers, json={"bp_sys": 160, "sleep": "poorly"})
    assert r.status_code == 200, r.text
    assert r.json()["values"]["bp_sys"] == 160 and r.json()["source"]["bp_sys"] == "override"
    assert kl.visit_level(rec, r.json()["values"])[0] == "ok"
    assert client.put(url, headers=auth_headers, json={"spo2": 140}).status_code == 400
    r = client.put(url, headers=auth_headers, json={"bp_sys": None, "sleep": None})
    assert r.json()["values"]["bp_sys"] == 130

    view = client.get(f"/api/v1/home-safety/clients/{elder.id}/kushlife", headers=auth_headers).json()
    assert view["baseline"]["values"]["spo2"] == 90 and view["latest_vitals"]["spo2"] == 90
    assert all(v["level"] == "ok" for v in view["visits"])  # 90% is normal for this client


# --- weekly summary ---------------------------------------------------------------


def test_draft_once_per_week_approval_gate_and_family(client, db, seed_tenant, auth_headers, monkeypatch):
    sent = []
    monkeypatch.setattr(en, "send", lambda to, title, body, *, family, background=True: sent.append((to, title, family)))
    elder = seed_tenant["elder"]
    _log(client, auth_headers, elder.id, _last_week_day(1), vitals={"bp_sys": 132, "bp_dia": 84, "spo2": 96})
    _log(client, auth_headers, elder.id, _last_week_day(3), settled=["poor_sleep"])

    assert kw.draft_weekly_summaries(db, now=_monday_8am() - timedelta(hours=2)) == []  # before 07:00 IST
    made = kw.draft_weekly_summaries(db, now=_monday_8am())
    assert len(made) == 1
    assert kw.draft_weekly_summaries(db, now=_monday_8am() + timedelta(minutes=2)) == []  # next tick: no duplicate
    rows = db.query(KushLifeWeekly).filter(KushLifeWeekly.elder_id == elder.id).all()
    assert len(rows) == 1 and rows[0].status == "draft"
    assert "Elder had 2 KushLife visits" in rows[0].text

    fh = _family(client, db, elder)
    week = client.get("/api/v1/home-safety/family/kushlife/week", headers=fh)
    assert week.status_code == 200, week.text
    assert week.json()["summary"] is None  # draft never shown
    assert week.json()["card"]["visits_done"] == 2

    pending = client.get("/api/v1/home-safety/clients/kushlife-weekly/pending", headers=auth_headers).json()
    assert [i["id"] for i in pending["items"]] == made
    assert pending["items"][0]["overdue"] is False or datetime.now(kw.IST) >= kw.overdue_at(rows[0].week_start)
    assert kw.as_dict(rows[0], now=kw.overdue_at(rows[0].week_start))["overdue"] is True

    base = f"/api/v1/home-safety/clients/{elder.id}/kushlife/weekly"
    lst = client.get(base, headers=auth_headers).json()
    assert lst["summaries"][0]["status"] == "draft"
    r = client.put(f"{base}/{made[0]}", headers=auth_headers, json={"text": "A calm week for Amma."})
    assert r.status_code == 200 and r.json()["text"] == "A calm week for Amma."
    weekly = lambda: [s for s in sent if s[2] and s[1].startswith("KushLife this week")]  # noqa: E731
    assert not weekly()  # nothing to the family yet

    r = client.post(f"{base}/{made[0]}/approve", headers=auth_headers, json={})
    assert r.status_code == 200, r.text
    fam_mail = weekly()
    assert fam_mail and "wk.fam@family.example" in fam_mail[0][0]
    assert client.post(f"{base}/{made[0]}/approve", headers=auth_headers).status_code == 409
    assert client.put(f"{base}/{made[0]}", headers=auth_headers, json={"text": "x"}).status_code == 400
    week = client.get("/api/v1/home-safety/family/kushlife/week", headers=fh).json()
    assert week["summary"]["text"] == "A calm week for Amma."
    assert client.get("/api/v1/home-safety/clients/kushlife-weekly/pending", headers=auth_headers).json()["items"] == []


def test_family_email_choice_respected(client, db, seed_tenant, auth_headers, monkeypatch):
    sent = []
    monkeypatch.setattr(en, "send", lambda to, title, body, *, family, background=True: sent.append((to, title, family)))
    elder = seed_tenant["elder"]
    _family(client, db, elder)
    en.save_family_prefs(db, elder, {"off": ["weekly_summary"]})
    _log(client, auth_headers, elder.id, _last_week_day(2))
    sid = kw.draft_weekly_summaries(db, now=_monday_8am())[0]
    r = client.post(f"/api/v1/home-safety/clients/{elder.id}/kushlife/weekly/{sid}/approve", headers=auth_headers)
    assert r.status_code == 200
    weekly = [to for to, title, fam in sent if fam and title.startswith("KushLife this week")]
    assert weekly == [[]]  # sent to nobody: the family turned weekly summaries off


def test_team_scope(client, db, seed_tenant, auth_headers, monkeypatch):
    monkeypatch.setattr(en, "send", lambda *a, **k: None)
    elder = seed_tenant["elder"]
    _log(client, auth_headers, elder.id, _last_week_day(2))
    sid = kw.draft_weekly_summaries(db, now=_monday_8am())[0]
    other = User(email="other.mgr@test.example", password_hash=hash_password("testpass123"),
                 first_name="Other", last_name="Mgr", role="CARE_MANAGER", tenant_id=seed_tenant["tenant"].id)
    db.add(other)
    db.commit()
    tok = client.post("/api/v1/auth/login", json={"email": "other.mgr@test.example", "password": "testpass123"})
    assert tok.status_code == 200, tok.text
    oh = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    assert client.get("/api/v1/home-safety/clients/kushlife-weekly/pending", headers=oh).json()["items"] == []
    base = f"/api/v1/home-safety/clients/{elder.id}/kushlife"
    assert client.get(f"{base}/weekly", headers=oh).status_code == 404
    assert client.post(f"{base}/weekly/{sid}/approve", headers=oh).status_code == 404
    assert client.put(f"{base}/baseline", headers=oh, json={"spo2": 95}).status_code == 404


# --- audit fixes --------------------------------------------------------------------


def test_client_without_kushlife_data_is_skipped_once(client, db, seed_tenant, auth_headers, monkeypatch):
    monkeypatch.setattr(en, "send", lambda *a, **k: None)
    elder = seed_tenant["elder"]
    from app.models.care_job import CareJob

    when = _last_week_day(2)
    db.add(CareJob(tenant_id=elder.tenant_id, elder_id=elder.id, kind="visit", title="Care visit",
                   scheduled_at=when, status="completed", completed_at=when))  # no KushLife record
    db.commit()
    calls = []
    real = kw.week_stats
    monkeypatch.setattr(kw, "week_stats", lambda *a, **k: calls.append(1) or real(*a, **k))
    assert kw.draft_weekly_summaries(db, now=_monday_8am()) == []
    assert kw.draft_weekly_summaries(db, now=_monday_8am() + timedelta(minutes=2)) == []
    assert calls == [1]  # the second tick doesn't recompute
    rows = db.query(KushLifeWeekly).filter(KushLifeWeekly.elder_id == elder.id).all()
    assert [r.status for r in rows] == ["skipped"]
    base = f"/api/v1/home-safety/clients/{elder.id}/kushlife/weekly"
    assert client.get(base, headers=auth_headers).json()["summaries"] == []
    assert client.get("/api/v1/home-safety/clients/kushlife-weekly/pending", headers=auth_headers).json()["items"] == []
    assert client.post(f"{base}/{rows[0].id}/approve", headers=auth_headers).status_code == 404


def test_approve_rejects_empty_text(client, db, seed_tenant, auth_headers, monkeypatch):
    monkeypatch.setattr(en, "send", lambda *a, **k: None)
    elder = seed_tenant["elder"]
    _log(client, auth_headers, elder.id, _last_week_day(2))
    sid = kw.draft_weekly_summaries(db, now=_monday_8am())[0]
    row = db.get(KushLifeWeekly, sid)
    row.text = "   "
    db.commit()
    url = f"/api/v1/home-safety/clients/{elder.id}/kushlife/weekly/{sid}/approve"
    r = client.post(url, headers=auth_headers, json={"text": "  "})
    assert r.status_code == 400 and "Write the summary before approving" in r.text
    db.expire_all()
    assert db.get(KushLifeWeekly, sid).status == "draft"
    assert client.post(url, headers=auth_headers, json={"text": "A good week."}).status_code == 200


def test_approve_is_atomic(client, db, seed_tenant, auth_headers, monkeypatch):
    import pytest
    from sqlalchemy import update

    sent = []
    monkeypatch.setattr(en, "send", lambda to, title, body, *, family, background=True: sent.append(title))
    elder = seed_tenant["elder"]
    _log(client, auth_headers, elder.id, _last_week_day(2))
    sid = kw.draft_weekly_summaries(db, now=_monday_8am())[0]
    row = db.get(KushLifeWeekly, sid)
    assert row.status == "draft"
    # Another request approves it after this one read the row (stale "draft" in memory).
    db.execute(update(KushLifeWeekly).where(KushLifeWeekly.id == sid).values(status="approved")
               .execution_options(synchronize_session=False))
    assert row.status == "draft"
    with pytest.raises(Exception) as exc:
        kw.approve_summary(db, elder, sid, seed_tenant["manager"])
    assert getattr(exc.value, "status_code", None) == 409
    assert not [t for t in sent if t.startswith("KushLife this week")]  # no second send
