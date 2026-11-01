"""K2 #88 family contact preferences and #91 "Call me" / "Ask about…"."""

from datetime import datetime, timezone

from app.core.security import hash_password
from app.livewell import email_notifications
from app.livewell.family_contacts import level_allows, render_times, email_time, save_contact
from app.livewell.family_elder_access import ensure_family_elder_link
from app.models.elder import Elder
from app.models.user import User


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _family_user(db, elder, tag):
    user = User(
        email=f"k2.{tag}@test.example",
        password_hash=hash_password("testpass123"),
        first_name=f"Fam{tag}",
        last_name="K2",
        role="ELDER_PORTAL",
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
    )
    db.add(user)
    db.flush()
    ensure_family_elder_link(db, user, elder)
    db.commit()
    return user


def _elder(db, tenant_id, tag, manager_id=None):
    e = Elder(tenant_id=tenant_id, first_name=f"Amma{tag}", last_name="K2", status="ACTIVE", manager_user_id=manager_id)
    db.add(e)
    db.commit()
    return e


def _capture(monkeypatch):
    sent = []

    def fake_send(to, title, body, *, family, background=True):
        sent.extend((t, title, body, family) for t in to)

    monkeypatch.setattr(email_notifications, "send", fake_send)
    return sent


# --- #88 levels -------------------------------------------------------------------


def test_level_allows_matrix():
    assert level_allows("everything", "visit")
    assert level_allows("important", "safety") and level_allows("important", "missed")
    assert level_allows("important", "order") and level_allows("important", "kushlife_red")
    assert level_allows("important", "sos")
    assert not level_allows("important", "visit") and not level_allows("important", "reply")
    assert level_allows("emergencies", "sos")
    assert not level_allows("emergencies", "safety") and not level_allows("emergencies", "missed")
    assert level_allows(None, "visit")  # no row = everything


def test_family_recipients_follow_each_persons_level(db, seed_tenant):
    elder = seed_tenant["elder"]
    a = _family_user(db, elder, "all")
    b = _family_user(db, elder, "imp")
    c = _family_user(db, elder, "sos")
    save_contact(db, elder, {"level": "important"}, user=b)
    save_contact(db, elder, {"level": "emergencies"}, user=c)
    email_notifications.save_family_prefs(db, elder, {"extra": ["abroad@test.example"]})
    save_contact(db, elder, {"level": "emergencies"}, email="abroad@test.example")
    db.commit()

    def who(event):
        return set(email_notifications.family_recipients(db, elder, event))

    assert who("visit") == {a.email}
    assert who("safety") == {a.email, b.email}
    assert who("missed") == {a.email, b.email}
    assert who("order") == {a.email, b.email}
    assert who("sos") == {a.email, b.email, c.email, "abroad@test.example"}


def test_my_details_saves_channel_timezone_level(db, client, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _family_user(db, elder, "me")
    h = _login(client, fam.email)
    res = client.put(
        "/api/v1/home-safety/family/my-details",
        headers=h,
        json={"phone": "+44 7700 900123", "channel": "sms", "timezone": "Europe/London", "level": "important"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["phone"], body["channel"], body["timezone"], body["level"]) == (
        "+44 7700 900123", "sms", "Europe/London", "important"
    )
    # Phone is mirrored for older readers (incident calls).
    db.refresh(elder)
    assert elder.custom_attributes["safe_home"]["family_phones"][str(fam.id)] == "+44 7700 900123"
    assert client.put("/api/v1/home-safety/family/my-details", headers=h, json={"timezone": "Mars/Base"}).status_code == 400
    assert client.put("/api/v1/home-safety/family/my-details", headers=h, json={"level": "loud"}).status_code == 400


def test_staff_edit_contact_and_team_scope(db, client, seed_tenant):
    elder = seed_tenant["elder"]
    fam = _family_user(db, elder, "staffedit")
    h = _login(client, seed_tenant["manager"].email)
    res = client.get(f"/api/v1/home-safety/clients/{elder.id}/family-contacts", headers=h)
    assert res.status_code == 200
    assert any(c["key"] == f"user:{fam.id}" for c in res.json())
    res = client.put(
        f"/api/v1/home-safety/clients/{elder.id}/family-contacts",
        headers=h,
        json={"key": f"user:{fam.id}", "level": "emergencies", "channel": "call", "timezone": "America/New_York"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["level"] == "emergencies"

    other_mgr = User(email="mgr2.k2@test.example", password_hash=hash_password("testpass123"), first_name="M",
                     last_name="Two", role="CARE_MANAGER", tenant_id=elder.tenant_id)
    db.add(other_mgr)
    db.commit()
    h2 = _login(client, other_mgr.email)
    assert client.get(f"/api/v1/home-safety/clients/{elder.id}/family-contacts", headers=h2).status_code == 404


def test_times_show_in_readers_timezone():
    at = datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc)  # 3:30 PM IST
    body = f"Visit on {email_time(at)}."
    assert render_times(body) == "Visit on Tue 6 Oct, 03:30 PM.".replace(" 0", " ")
    london = render_times(body, "Europe/London")
    assert "11:00 AM London time" in london and "3:30 PM IST" in london


def test_family_email_groups_by_timezone(db, seed_tenant, monkeypatch):
    elder = seed_tenant["elder"]
    a = _family_user(db, elder, "tzin")
    b = _family_user(db, elder, "tzuk")
    save_contact(db, elder, {"timezone": "Europe/London"}, user=b)
    db.commit()
    delivered = []
    monkeypatch.setattr(email_notifications, "_deliver", lambda to, subject, text, page: delivered.extend((t, text) for t in to))
    at = datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc)
    with email_notifications.email_context("", "Amma", email_notifications.family_timezones(db, elder)):
        email_notifications.send([a.email, b.email], "Visit", f"On {email_time(at)}", family=True, background=False)
    texts = dict(delivered)
    assert "London time" not in texts[a.email] and "3:30 PM" in texts[a.email]
    assert "11:00 AM London time" in texts[b.email]


# --- #91 questions ------------------------------------------------------------------


def test_call_me_siblings_see_question_and_reply(db, client, seed_tenant, monkeypatch):
    sent = _capture(monkeypatch)
    elder = seed_tenant["elder"]
    a = _family_user(db, elder, "sibA")
    b = _family_user(db, elder, "sibB")
    save_contact(db, elder, {"level": "emergencies"}, user=b)
    db.commit()
    ha, hb = _login(client, a.email), _login(client, b.email)

    res = client.post("/api/v1/home-safety/family/questions", headers=ha,
                      json={"kind": "call_me", "window": "evening", "day": "today", "body": "About her knee"})
    assert res.status_code == 200, res.text
    q = res.json()
    assert q["status"] == "open" and q["call_window"] == "Today evening, 5–8 PM IST"
    # The client's care manager is emailed (staff event family_question); admins are not by default.
    staff_to = {t for t, _ti, _b, fam in sent if not fam}
    assert seed_tenant["manager"].email in staff_to
    assert seed_tenant["admin"].email not in staff_to

    # Sibling sees it (not theirs); it is in the Messages thread too.
    rows = client.get("/api/v1/home-safety/family/questions", headers=hb).json()
    assert [r["id"] for r in rows] == [q["id"]] and rows[0]["is_mine"] is False
    msgs = client.get("/api/v1/home-safety/family/messages", headers=hb).json()
    assert any("Please call me" in m["body"] for m in msgs)

    # Ops dashboard: Needs attention.
    hm = _login(client, seed_tenant["manager"].email)
    att = client.get("/api/v1/home-safety/dashboard/attention", headers=hm)
    assert att.status_code == 200, att.text
    assert any(r["id"] == q["id"] for r in att.json()["questions"])
    assert att.json()["counts"]["questions"] == 1

    sent.clear()
    res = client.post(f"/api/v1/home-safety/clients/{elder.id}/questions/{q['id']}/reply", headers=hm,
                      json={"body": "Calling you at 6 PM."})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "done"
    rows = client.get("/api/v1/home-safety/family/questions", headers=hb).json()
    assert rows[0]["reply"] == "Calling you at 6 PM."
    msgs = client.get("/api/v1/home-safety/family/messages", headers=hb).json()
    assert any(m["body"] == "Calling you at 6 PM." and m["sender_role"] == "team" for m in msgs)
    # Asker always gets the reply; the emergencies-only sibling does not get the email.
    fam_to = {t for t, _ti, _b, fam in sent if fam}
    assert a.email in fam_to and b.email not in fam_to


def test_ask_about_visit_and_household_isolation(db, client, seed_tenant, monkeypatch):
    _capture(monkeypatch)
    elder = seed_tenant["elder"]
    a = _family_user(db, elder, "askA")
    other = _elder(db, elder.tenant_id, "Other", seed_tenant["manager"].id)
    c = _family_user(db, other, "otherC")
    ha, hc = _login(client, a.email), _login(client, c.email)

    assert client.post("/api/v1/home-safety/family/questions", headers=ha, json={"kind": "ask"}).status_code == 400
    res = client.post("/api/v1/home-safety/family/questions", headers=ha,
                      json={"kind": "ask", "body": "Was she eating well?", "visit_ref": "12",
                            "visit_label": "Wellness visit, 5 Oct", "flag_key": "visit:12"})
    assert res.status_code == 200, res.text
    q = res.json()
    assert q["visit_label"] == "Wellness visit, 5 Oct"

    # Another household sees nothing and cannot reach the question through staff routes.
    assert client.get("/api/v1/home-safety/family/questions", headers=hc).json() == []
    assert client.post(f"/api/v1/home-safety/clients/{elder.id}/questions/{q['id']}/done", headers=hc).status_code == 403
    # Staff on the wrong client id get 404.
    hm = _login(client, seed_tenant["manager"].email)
    assert client.post(f"/api/v1/home-safety/clients/{other.id}/questions/{q['id']}/done", headers=hm).status_code == 404


def test_staff_outside_team_cannot_reply(db, client, seed_tenant, monkeypatch):
    _capture(monkeypatch)
    elder = seed_tenant["elder"]
    a = _family_user(db, elder, "teamA")
    ha = _login(client, a.email)
    q = client.post("/api/v1/home-safety/family/questions", headers=ha, json={"kind": "call_me"}).json()
    other_mgr = User(email="mgr3.k2@test.example", password_hash=hash_password("testpass123"), first_name="M",
                     last_name="Three", role="CARE_MANAGER", tenant_id=elder.tenant_id)
    db.add(other_mgr)
    db.commit()
    h2 = _login(client, other_mgr.email)
    url = f"/api/v1/home-safety/clients/{elder.id}/questions/{q['id']}"
    assert client.post(url + "/reply", headers=h2, json={"body": "hi"}).status_code == 404
    assert client.post(url + "/done", headers=h2).status_code == 404
    # The admin (all clients) can mark it done; it leaves the attention list.
    hadm = _login(client, seed_tenant["admin"].email)
    res = client.post(url + "/done", headers=hadm)
    assert res.status_code == 200 and res.json()["status"] == "done"
    from app.livewell.family_questions import open_for_elders

    assert open_for_elders(db, [elder]) == []


def test_question_event_listed_in_settings(db, seed_tenant):
    rules = email_notifications.get_rules(seed_tenant["tenant"])
    assert rules["staff"]["family_question"] == {"enabled": True, "manager": True, "admins": False, "extra": []}


# --- audit fixes --------------------------------------------------------------------


def test_level_lookup_error_sends_to_everyone_and_keeps_transaction(db, seed_tenant, monkeypatch):
    from sqlalchemy import text

    from app.livewell import family_contacts as fc

    elder = seed_tenant["elder"]
    a = _family_user(db, elder, "errA")
    b = _family_user(db, elder, "errB")
    save_contact(db, elder, {"level": "emergencies"}, user=b)
    db.commit()
    calls = []

    def broken(db_, elder_):
        calls.append(1)
        db_.execute(text("SELECT * FROM no_such_table"))  # a real failing query

    monkeypatch.setattr(fc, "prefs_by_email", broken)
    # Emergencies never look at levels.
    assert {a.email, b.email} <= set(email_notifications.family_recipients(db, elder, "sos"))
    assert calls == []
    # A failed lookup: everyone gets it (as "everything"), and the session still works.
    assert {a.email, b.email} <= set(email_notifications.family_recipients(db, elder, "visit"))
    assert calls == [1]
    assert db.get(Elder, elder.id).id == elder.id


def test_staff_question_reply_keeps_messages_unread(db, client, seed_tenant, monkeypatch):
    from app.livewell.family_care_hub import FamilyCareHubService, _hub

    _capture(monkeypatch)
    elder = seed_tenant["elder"]
    a = _family_user(db, elder, "unrd")
    ha = _login(client, a.email)
    assert client.post("/api/v1/home-safety/family/messages", headers=ha, json={"body": "Unrelated note"}).status_code == 200
    q = client.post("/api/v1/home-safety/family/questions", headers=ha, json={"kind": "call_me"}).json()
    hm = _login(client, seed_tenant["manager"].email)
    res = client.post(f"/api/v1/home-safety/clients/{elder.id}/questions/{q['id']}/reply", headers=hm,
                      json={"body": "Will call."})
    assert res.status_code == 200, res.text
    db.expire_all()
    hub = _hub(db.get(Elder, elder.id))
    assert not hub.get("staff_read_at")
    assert FamilyCareHubService._unread_by_staff(hub) >= 1


def test_prefs_by_email_prefers_login_row_and_unique_rows(db, seed_tenant):
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.livewell.family_contacts import prefs_by_email
    from app.models.family_contact import FamilyContact

    elder = seed_tenant["elder"]
    a = _family_user(db, elder, "dupe")
    # An email-only row for the same address, older than the login's own row.
    db.add(FamilyContact(tenant_id=elder.tenant_id, elder_id=elder.id, email=a.email.lower(), level="emergencies",
                         channel="email", timezone="Asia/Kolkata"))
    db.commit()
    save_contact(db, elder, {"level": "important"}, user=a)
    db.commit()
    assert prefs_by_email(db, elder)[a.email.lower()]["level"] == "important"
    # Saving again edits the same row; a second row for the login is refused by the index.
    save_contact(db, elder, {"level": "everything"}, user=a)
    db.commit()
    assert db.query(FamilyContact).filter_by(elder_id=elder.id, user_id=a.id).count() == 1
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(FamilyContact(tenant_id=elder.tenant_id, elder_id=elder.id, user_id=a.id, email=a.email,
                                 level="everything", channel="email", timezone="Asia/Kolkata"))
            db.flush()
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(FamilyContact(tenant_id=elder.tenant_id, elder_id=elder.id, email=a.email.lower(),
                                 level="everything", channel="email", timezone="Asia/Kolkata"))
            db.flush()


def test_message_reply_always_reaches_its_author(db, client, seed_tenant, monkeypatch):
    sent = _capture(monkeypatch)
    elder = seed_tenant["elder"]
    a = _family_user(db, elder, "authA")
    b = _family_user(db, elder, "authB")
    save_contact(db, elder, {"level": "emergencies"}, user=a)
    save_contact(db, elder, {"level": "emergencies"}, user=b)
    db.commit()
    ha = _login(client, a.email)
    assert client.post("/api/v1/home-safety/family/messages", headers=ha, json={"body": "How was today?"}).status_code == 200
    sent.clear()
    hm = _login(client, seed_tenant["manager"].email)
    res = client.post(f"/api/v1/home-safety/care/family-messages/{elder.id}/reply", headers=hm, json={"body": "All well."})
    assert res.status_code == 200, res.text
    fam_to = {t for t, _ti, _b, fam in sent if fam}
    assert a.email in fam_to and b.email not in fam_to


def test_staff_question_has_phone_and_ist_window(db, client, seed_tenant, monkeypatch):
    from app.livewell.family_questions import ist_span

    _capture(monkeypatch)
    elder = seed_tenant["elder"]
    a = _family_user(db, elder, "uk")
    save_contact(db, elder, {"timezone": "Europe/London", "phone": "+44 7700 900123"}, user=a)
    db.commit()
    # London is UTC+1 on 6 Oct 2026: 5–8 PM London = 9:30 PM–12:30 AM IST.
    assert ist_span("evening", "today", "Europe/London", datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)) == (
        "9:30 PM–12:30 AM IST"
    )
    ha = _login(client, a.email)
    q = client.post("/api/v1/home-safety/family/questions", headers=ha,
                    json={"kind": "call_me", "window": "evening", "day": "today"}).json()
    assert q["call_window"].startswith("Today evening, 5–8 PM London time (") and q["call_window"].endswith(" IST)")
    assert "asker_phone" not in q  # family views never carry phones
    hm = _login(client, seed_tenant["manager"].email)
    rows = client.get(f"/api/v1/home-safety/clients/{elder.id}/questions", headers=hm).json()
    assert rows[0]["asker_phone"] == "+44 7700 900123"
    att = client.get("/api/v1/home-safety/dashboard/attention", headers=hm).json()
    assert att["questions"][0]["asker_phone"] == "+44 7700 900123"
