"""KushLife K1: capture, flags, family view, score explanation and journey."""

from datetime import datetime, timedelta, timezone

from app.livewell import email_notifications as en


def _job(client, headers, elder_id, kind="visit"):
    when = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    res = client.post("/api/v1/jobs", json={"elder_id": elder_id, "kind": kind, "scheduled_at": when}, headers=headers)
    assert res.status_code == 201, res.text
    job = res.json()
    client.post(f"/api/v1/jobs/{job['id']}/progress", json={"status": "checked_in"}, headers=headers)
    return job


def _kl(**changed):
    checks = {k: {"status": "ok"} for k in ("safe", "steady", "settled", "connected")}
    for k, chips in changed.items():
        checks[k] = {"status": "concern", "chips": chips}
    return {"checks": checks, "sleep": "well", "appetite": "usual", "vitals": {"spo2": 97}}


def test_every_check_must_be_answered(client, seed_tenant, auth_headers):
    job = _job(client, auth_headers, seed_tenant["elder"].id)
    bad = client.post(f"/api/v1/jobs/{job['id']}/report", headers=auth_headers,
                      json={"kushlife": {"checks": {"safe": {"status": "ok"}}}})
    assert bad.status_code == 400 and "Steady" in bad.text


def test_trend_flags_and_family_view(client, db, seed_tenant, auth_headers, monkeypatch):
    elder = seed_tenant["elder"]
    elder.manager_user_id = seed_tenant["manager"].id
    db.commit()
    sent = []
    monkeypatch.setattr(en, "send", lambda to, title, body, *, family, background=True: sent.append((title, family)))

    # Visit 1: all as usual. Visits 2-3: Steady changed → amber (2 of last 3).
    job = _job(client, auth_headers, elder.id)
    assert client.post(f"/api/v1/jobs/{job['id']}/report", headers=auth_headers,
                       json={"kushlife": _kl(), "note": "Good day"}).status_code == 200
    for _ in range(2):
        job = _job(client, auth_headers, elder.id)
        r = client.post(f"/api/v1/jobs/{job['id']}/report", headers=auth_headers,
                        json={"kushlife": _kl(steady=["unsteady"]), "note": "Wobbly"})
        assert r.status_code == 200, r.text
    staff = client.get(f"/api/v1/home-safety/clients/{elder.id}/kushlife", headers=auth_headers).json()
    amber = [f for f in staff["flags"] if f["level"] == "amber"]
    assert amber and "Steady" in amber[0]["reason"]
    assert staff["visits"][0]["chips"]["steady"] == ["Unsteady walking"]
    assert any(t.startswith("KushLife amber") for t, fam in sent if not fam)

    ack = client.post(f"/api/v1/home-safety/clients/{elder.id}/kushlife/acknowledge", headers=auth_headers,
                      json={"key": amber[0]["key"]})
    assert ack.status_code == 200, ack.text
    assert any("keeping an eye" in t.lower() for t, fam in sent if fam)

    # A fall is red at once: family hears the 2-hour call promise.
    sent.clear()
    job = _job(client, auth_headers, elder.id)
    client.post(f"/api/v1/jobs/{job['id']}/report", headers=auth_headers, json={"kushlife": _kl(steady=["fall"])})
    assert any(t == "KushLife: we'll call you" for t, fam in sent if fam)

    admin = client.post("/api/v1/auth/login", json={"email": "admin@test.example", "password": "testpass123"}).json()
    ah = {"Authorization": f"Bearer {admin['access_token']}"}
    client.post(f"/api/v1/team/clients/{elder.id}/family-logins", headers=ah,
                json={"email": "kl.fam@family.example", "password": "familypass1"})
    fam = client.post("/api/v1/auth/login", json={"email": "kl.fam@family.example", "password": "familypass1"}).json()
    fh = {"Authorization": f"Bearer {fam['access_token']}"}
    view = client.get("/api/v1/home-safety/family/kushlife", headers=fh).json()
    assert len(view["visits"]) == 4 and view["status"] == "We're calling you"
    assert "within 2 hours" in view["summary_line"]

    why = client.get("/api/v1/home-safety/family/score-explain", headers=fh)
    assert why.status_code == 200 and "how" in why.json()
    journey = client.get("/api/v1/home-safety/family/journey", headers=fh)
    assert journey.status_code == 200, journey.text
    assert [s["key"] for s in journey.json()["steps"]] == ["assess", "fixes", "installed", "kushlife", "reassess"]


def test_no_silent_all_ok_and_past_visit_sends_no_live_alert(client, db, seed_tenant, auth_headers, monkeypatch):
    elder = seed_tenant["elder"]
    job = _job(client, auth_headers, elder.id)
    assert client.post(f"/api/v1/jobs/{job['id']}/report", headers=auth_headers, json={"note": "x"}).status_code == 400
    assert client.post(f"/api/v1/jobs/{job['id']}/report", headers=auth_headers,
                       json={"checks": {"safe": "ok"}}).status_code == 400

    sent = []
    monkeypatch.setattr(en, "send", lambda to, title, body, *, family, background=True: sent.append((title, family)))
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    res = client.post("/api/v1/jobs/log-past", headers=auth_headers,
                      json={"elder_id": elder.id, "visited_at": week_ago, "kushlife": _kl(steady=["fall"])})
    assert res.status_code == 201, res.text
    assert not any(t == "KushLife: we'll call you" for t, _f in sent)  # old news: no 2-hour promise


def test_streak_flag_is_sent_once(client, db, seed_tenant, auth_headers, monkeypatch):
    elder = seed_tenant["elder"]
    sent = []
    monkeypatch.setattr(en, "send", lambda to, title, body, *, family, background=True: sent.append((title, family)))
    for _ in range(4):
        job = _job(client, auth_headers, elder.id)
        client.post(f"/api/v1/jobs/{job['id']}/report", headers=auth_headers, json={"kushlife": _kl(settled=["ate_less"])})
    staff_flags = [t for t, fam in sent if not fam and t.startswith("KushLife")]
    # amber at visit 2, red at visit 3 (3 in a row) — visit 4 continues the same streak: no new email.
    assert len(staff_flags) == 2, staff_flags
