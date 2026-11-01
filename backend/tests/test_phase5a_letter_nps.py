"""K3 + Phase 5 (#100 #106): monthly letter, voice notes, vitals trend, visit rating, NPS, quality."""

from datetime import datetime, time, timedelta, timezone

from app.core.security import hash_password
from app.livewell import email_notifications as en
from app.livewell import kushlife as kl
from app.livewell import kushlife_monthly as km
from app.livewell import visit_feedback as fb
from app.models.kushlife_quality import KushLifeMonthly
from app.models.user import User

IST = km.IST
WEBM = b"\x1aE\xdf\xa3webm"  # EBML magic: uploads are sniffed


def _kl(vitals=None):
    return {"checks": {k: {"status": "ok"} for k in kl.CHECKS}, "sleep": "well", "appetite": "usual",
            "vitals": vitals or {"bp_sys": 130, "bp_dia": 82, "spo2": 97, "pulse": 74}}


def _log(client, headers, elder_id, when, vitals=None) -> int:
    res = client.post("/api/v1/jobs/log-past", headers=headers,
                      json={"elder_id": elder_id, "visited_at": when.isoformat(), "kushlife": _kl(vitals)})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _last_month_day(n: int) -> datetime:
    return datetime.combine(km.last_month_start() + timedelta(days=n), time(10, 0), tzinfo=IST)


def _first_8am() -> datetime:
    return datetime.combine(datetime.now(IST).date().replace(day=1), time(8, 0), tzinfo=IST)


def _family(client, elder, email="m5.fam@family.example"):
    admin = client.post("/api/v1/auth/login", json={"email": "admin@test.example", "password": "testpass123"}).json()
    ah = {"Authorization": f"Bearer {admin['access_token']}"}
    r = client.post(f"/api/v1/team/clients/{elder.id}/family-logins", headers=ah,
                    json={"email": email, "password": "familypass1"})
    assert r.status_code in (200, 201), r.text
    fam = client.post("/api/v1/auth/login", json={"email": email, "password": "familypass1"}).json()
    return {"Authorization": f"Bearer {fam['access_token']}"}


def _other_manager(client, db, seed_tenant):
    db.add(User(email="other5.mgr@test.example", password_hash=hash_password("testpass123"),
                first_name="Other", last_name="Mgr", role="CARE_MANAGER", tenant_id=seed_tenant["tenant"].id))
    db.commit()
    tok = client.post("/api/v1/auth/login", json={"email": "other5.mgr@test.example", "password": "testpass123"})
    return {"Authorization": f"Bearer {tok.json()['access_token']}"}


# --- monthly letter -------------------------------------------------------------------


def test_letter_drafted_once_per_month_and_approval_gate(client, db, seed_tenant, auth_headers, monkeypatch):
    sent = []
    monkeypatch.setattr(en, "send", lambda to, title, body, *, family, background=True: sent.append((to, title, family)))
    elder = seed_tenant["elder"]
    _log(client, auth_headers, elder.id, _last_month_day(2))
    _log(client, auth_headers, elder.id, _last_month_day(9), vitals={"bp_sys": 136, "bp_dia": 84, "spo2": 96})

    assert km.draft_monthly_letters(db, now=_first_8am() - timedelta(hours=2)) == []  # before 07:00 IST on the 1st
    made = km.draft_monthly_letters(db, now=_first_8am())
    assert len(made) == 1
    assert km.draft_monthly_letters(db, now=_first_8am() + timedelta(minutes=2)) == []  # dedupe
    assert km.draft_monthly_letters(db, now=_first_8am() + timedelta(days=3)) == []
    rows = db.query(KushLifeMonthly).filter(KushLifeMonthly.elder_id == elder.id).all()
    assert len(rows) == 1 and rows[0].status == "draft"
    assert "Elder had 2 visits this month" in rows[0].text
    assert rows[0].stats["kushlife_visits"] == 2

    fh = _family(client, elder)
    assert client.get("/api/v1/home-safety/family/kushlife/letters", headers=fh).json() == []
    assert client.get(f"/api/v1/home-safety/family/kushlife/letters/{made[0]}", headers=fh).status_code == 404
    assert client.get(f"/api/v1/home-safety/family/kushlife/letters/{made[0]}/pdf", headers=fh).status_code == 404

    pending = client.get("/api/v1/home-safety/quality/monthly-pending", headers=auth_headers).json()
    assert [i["id"] for i in pending["items"]] == made

    base = f"/api/v1/home-safety/clients/{elder.id}/kushlife/monthly"
    r = client.put(f"{base}/{made[0]}", headers=auth_headers,
                   json={"text": "A steady month for Amma.", "manager_note": "Lovely to see her walking."})
    assert r.status_code == 200 and r.json()["manager_note"] == "Lovely to see her walking."
    assert not [s for s in sent if s[2] and s[1].startswith("KushLife letter")]
    r = client.post(f"{base}/{made[0]}/approve", headers=auth_headers, json={})
    assert r.status_code == 200, r.text
    assert [s for s in sent if s[2] and s[1].startswith("KushLife letter")]
    assert client.post(f"{base}/{made[0]}/approve", headers=auth_headers).status_code == 409
    assert client.put(f"{base}/{made[0]}", headers=auth_headers, json={"text": "x"}).status_code == 400

    lst = client.get("/api/v1/home-safety/family/kushlife/letters", headers=fh).json()
    assert [x["id"] for x in lst] == made
    one = client.get(f"/api/v1/home-safety/family/kushlife/letters/{made[0]}", headers=fh).json()
    assert one["text"] == "A steady month for Amma." and "draft_text" not in one
    pdf = client.get(f"/api/v1/home-safety/family/kushlife/letters/{made[0]}/pdf", headers=fh)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_vitals_series_staff_and_family(client, db, seed_tenant, auth_headers, monkeypatch):
    monkeypatch.setattr(en, "send", lambda *a, **k: None)
    elder = seed_tenant["elder"]
    now = datetime.now(IST)
    _log(client, auth_headers, elder.id, now - timedelta(days=120))  # older than 3 months: left out
    for d in (40, 20, 5):
        _log(client, auth_headers, elder.id, now - timedelta(days=d), vitals={"bp_sys": 128 + d, "bp_dia": 80, "spo2": 96})
    s = client.get(f"/api/v1/home-safety/clients/{elder.id}/kushlife/vitals", headers=auth_headers).json()
    assert [p["bp_sys"] for p in s["points"]] == [168, 148, 133]  # oldest first
    fh = _family(client, elder)
    f = client.get("/api/v1/home-safety/family/kushlife/vitals", headers=fh).json()
    assert len(f["points"]) == 3 and "bp_sys" in f["baseline"]


# --- voice notes ---------------------------------------------------------------------


def test_voice_note_family_only_when_shared(client, db, seed_tenant, auth_headers, monkeypatch):
    monkeypatch.setattr(en, "send", lambda *a, **k: None)
    elder = seed_tenant["elder"]
    job_id = _log(client, auth_headers, elder.id, datetime.now(IST) - timedelta(days=1))
    up = client.post(f"/api/v1/jobs/{job_id}/voice-notes", headers=auth_headers,
                     files={"file": ("note.webm", b"\x1aE\xdf\xa3fake-webm", "audio/webm;codecs=opus")},
                     data={"duration_s": "12"})
    assert up.status_code == 200, up.text
    note = up.json()
    assert note["share_with_family"] is False and note["duration_s"] == 12
    bad = client.post(f"/api/v1/jobs/{job_id}/voice-notes", headers=auth_headers,
                      files={"file": ("x.txt", b"hello", "text/plain")})
    assert bad.status_code == 400
    long_ = client.post(f"/api/v1/jobs/{job_id}/voice-notes", headers=auth_headers,
                        files={"file": ("n.ogg", b"OggS", "audio/ogg")}, data={"duration_s": "95"})
    assert long_.status_code == 400

    audio = client.get(f"/api/v1/home-safety/voice-notes/{note['id']}/audio", headers=auth_headers)
    assert audio.status_code == 200 and audio.headers["content-type"].startswith("audio/webm")

    fh = _family(client, elder)
    fam_url = f"/api/v1/home-safety/family/voice-notes/{note['id']}/audio"
    assert client.get(fam_url, headers=fh).status_code == 404
    visit = client.get(f"/api/v1/home-safety/family/visits/job-{job_id}", headers=fh)
    assert visit.status_code == 200, visit.text
    assert visit.json()["voice_notes"] == []

    r = client.post(f"/api/v1/home-safety/voice-notes/{note['id']}/share", headers=auth_headers, json={"share": True})
    assert r.status_code == 200 and r.json()["share_with_family"] is True
    assert client.get(fam_url, headers=fh).status_code == 200
    assert len(client.get(f"/api/v1/home-safety/family/visits/job-{job_id}", headers=fh).json()["voice_notes"]) == 1


# --- rating, NPS, attention -------------------------------------------------------------


def test_rating_once_per_visit_and_low_rating_in_attention(client, db, seed_tenant, auth_headers, monkeypatch):
    monkeypatch.setattr(en, "send", lambda *a, **k: None)
    elder = seed_tenant["elder"]
    job_id = _log(client, auth_headers, elder.id, datetime.now(IST) - timedelta(hours=5))
    fh = _family(client, elder)
    sched = client.get("/api/v1/home-safety/family/schedule", headers=fh).json()
    item = next(v for v in sched["recent"] if v["id"] == f"job-{job_id}")
    assert item["can_rate"] is True

    url = f"/api/v1/home-safety/family/visits/job-{job_id}/experience-rating"
    r = client.post(url, headers=fh, json={"rating": 2, "comment": "Came late"})
    assert r.status_code == 200, r.text
    assert r.json()["experience_rating"] == 2 and r.json()["can_rate"] is False
    assert client.post(url, headers=fh, json={"rating": 5}).status_code == 409  # once per visit per person
    # A second family member can rate the same visit.
    fh2 = _family(client, elder, email="m5.sib@family.example")
    assert client.post(url, headers=fh2, json={"rating": 5}).status_code == 200

    att = client.get("/api/v1/home-safety/dashboard/attention", headers=auth_headers).json()
    rows = [f for f in att["feedback"] if f["kind"] == "rating"]
    assert len(rows) == 1 and rows[0]["score"] == 2 and rows[0]["comment"] == "Came late"
    assert att["counts"]["feedback"] == 1

    q = client.get(f"/api/v1/home-safety/clients/{elder.id}/quality", headers=auth_headers).json()
    assert q["avg_rating"] == 3.5 and q["ratings"] == 2 and q["kushlife_pct"] == 100

    r = client.post(f"/api/v1/home-safety/feedback/rating/{rows[0]['id']}/review", headers=auth_headers)
    assert r.status_code == 200
    att = client.get("/api/v1/home-safety/dashboard/attention", headers=auth_headers).json()
    assert att["feedback"] == []


def test_nps_every_90_days_and_detractor_in_attention(client, db, seed_tenant, auth_headers, monkeypatch):
    monkeypatch.setattr(en, "send", lambda *a, **k: None)
    elder = seed_tenant["elder"]
    fh = _family(client, elder)
    assert client.get("/api/v1/home-safety/family/feedback/nps", headers=fh).json()["due"] is False  # no visit yet
    _log(client, auth_headers, elder.id, datetime.now(IST) - timedelta(days=2))
    assert client.get("/api/v1/home-safety/family/feedback/nps", headers=fh).json()["due"] is True
    r = client.post("/api/v1/home-safety/family/feedback/nps", headers=fh, json={"score": 4, "reason": "Too costly"})
    assert r.status_code == 200, r.text
    assert client.get("/api/v1/home-safety/family/feedback/nps", headers=fh).json()["due"] is False
    assert client.post("/api/v1/home-safety/family/feedback/nps", headers=fh, json={"score": 9}).status_code == 409

    fam = db.query(User).filter(User.email == "m5.fam@family.example").one()
    later = datetime.now(timezone.utc) + timedelta(days=91)
    assert fb.nps_status(db, fam, elder, now=later)["due"] is True

    att = client.get("/api/v1/home-safety/dashboard/attention", headers=auth_headers).json()
    assert [(f["kind"], f["score"]) for f in att["feedback"]] == [("nps", 4)]
    agency = client.get("/api/v1/home-safety/quality", headers=auth_headers).json()
    assert agency["nps"]["responses"] == 1 and agency["nps"]["nps"] == -100


# --- team scope -------------------------------------------------------------------------


def test_team_scope(client, db, seed_tenant, auth_headers, monkeypatch):
    monkeypatch.setattr(en, "send", lambda *a, **k: None)
    elder = seed_tenant["elder"]
    job_id = _log(client, auth_headers, elder.id, _last_month_day(3))
    lid = km.draft_monthly_letters(db, now=_first_8am())[0]
    note = client.post(f"/api/v1/jobs/{job_id}/voice-notes", headers=auth_headers,
                       files={"file": ("n.webm", WEBM, "audio/webm")}).json()
    fh = _family(client, elder)
    client.post(f"/api/v1/home-safety/family/visits/job-{job_id}/experience-rating", headers=fh, json={"rating": 1})

    oh = _other_manager(client, db, seed_tenant)
    base = f"/api/v1/home-safety/clients/{elder.id}"
    assert client.get("/api/v1/home-safety/quality/monthly-pending", headers=oh).json()["items"] == []
    assert client.get(f"{base}/kushlife/monthly", headers=oh).status_code == 404
    assert client.post(f"{base}/kushlife/monthly/{lid}/approve", headers=oh).status_code == 404
    assert client.get(f"{base}/kushlife/monthly/{lid}/pdf", headers=oh).status_code == 404
    assert client.get(f"{base}/kushlife/vitals", headers=oh).status_code == 404
    assert client.get(f"{base}/voice-notes", headers=oh).status_code == 404
    assert client.get(f"/api/v1/home-safety/voice-notes/{note['id']}/audio", headers=oh).status_code == 404
    assert client.post(f"/api/v1/home-safety/voice-notes/{note['id']}/share", headers=oh,
                       json={"share": True}).status_code == 404
    assert client.post(f"/api/v1/jobs/{job_id}/voice-notes", headers=oh,
                       files={"file": ("n.webm", WEBM, "audio/webm")}).status_code == 404
    assert client.get("/api/v1/home-safety/dashboard/attention", headers=oh).json()["feedback"] == []
    rid = fb.attention_rows(db, [elder])[0]["id"]
    assert client.post(f"/api/v1/home-safety/feedback/rating/{rid}/review", headers=oh).status_code == 404
    agency = client.get("/api/v1/home-safety/quality", headers=oh).json()
    assert agency["clients"] == [] and agency["agency"]["visits_done"] == 0


def test_voice_note_size_cap_magic_bytes_and_per_visit_cap(client, db, seed_tenant, auth_headers, monkeypatch):
    from app.livewell import visit_feedback as fb

    monkeypatch.setattr(en, "send", lambda *a, **k: None)
    elder = seed_tenant["elder"]
    job_id = _log(client, auth_headers, elder.id, datetime.now(IST) - timedelta(days=2))
    url = f"/api/v1/jobs/{job_id}/voice-notes"
    big = b"\x1aE\xdf\xa3" + b"0" * (fb.VOICE_MAX_BYTES + 10)
    assert client.post(url, headers=auth_headers, files={"file": ("n.webm", big, "audio/webm")}).status_code == 413
    # Claims webm but is not.
    fake = client.post(url, headers=auth_headers, files={"file": ("n.webm", b"<html>x</html>", "audio/webm")})
    assert fake.status_code == 400
    # Claims ogg but is webm.
    assert client.post(url, headers=auth_headers,
                       files={"file": ("n.ogg", b"\x1aE\xdf\xa3abc", "audio/ogg")}).status_code == 400
    assert fb.sniff_audio(b"\x00\x00\x00\x1cftypM4A ") == "mp4"
    assert fb.sniff_audio(b"OggS\x00") == "ogg"
    ok = [client.post(url, headers=auth_headers, files={"file": ("n.m4a", b"\x00\x00\x00\x1cftypM4A data", "audio/mp4")})
          for _ in range(fb.VOICE_PER_JOB)]
    assert all(r.status_code == 200 for r in ok), [r.text for r in ok]
    over = client.post(url, headers=auth_headers, files={"file": ("n.ogg", b"OggS data", "audio/ogg")})
    assert over.status_code == 400 and "up to" in over.text
