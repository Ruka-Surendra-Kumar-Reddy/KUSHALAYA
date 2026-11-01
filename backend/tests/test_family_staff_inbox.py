"""Staff inbox for family messages: unread counts, replies, tenant scoping, email."""

from app.core.security import hash_password
from app.livewell import family_care_hub
from app.livewell.family_elder_access import ensure_family_elder_link
from app.models.elder import Elder
from app.models.tenant import Tenant
from app.models.user import User


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _family(db, tenant_id, tag):
    manager = db.query(User).filter(User.tenant_id == tenant_id, User.role == "CARE_MANAGER").first()
    elder = Elder(
        tenant_id=tenant_id,
        first_name=f"Elder{tag}",
        last_name="Inbox",
        status="ACTIVE",
        manager_user_id=manager.id if manager else None,
    )
    db.add(elder)
    db.flush()
    user = User(
        email=f"family.{tag}.inbox@test.example",
        password_hash=hash_password("testpass123"),
        first_name=f"Fam{tag}",
        last_name="Member",
        role="ELDER_PORTAL",
        tenant_id=tenant_id,
        elder_id=elder.id,
    )
    db.add(user)
    db.flush()
    ensure_family_elder_link(db, user, elder)
    db.commit()
    return user, elder


class _RecordingEmail:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, body, html=None):
        self.sent.append((to, subject, body))

        class R:
            success = True
            detail = "ok"

        return R()


def test_family_message_reaches_staff_inbox_and_email(db, client, seed_tenant, monkeypatch):
    tenant = seed_tenant["tenant"]
    fam, elder = _family(db, tenant.id, "a")
    elder.manager_user_id = seed_tenant["manager"].id  # the client's care manager
    db.commit()
    from app.livewell import email_notifications

    sent = []
    monkeypatch.setattr(
        email_notifications, "send", lambda to, title, body, *, family, background=True: sent.extend((t, title, body) for t in to)
    )

    fam_headers = _login(client, fam.email)
    res = client.post(
        "/api/v1/home-safety/family/messages",
        headers=fam_headers,
        json={"body": "Can someone check the grab bar?"},
    )
    assert res.status_code == 200, res.text

    recipients = {to for to, _s, _b in sent}
    assert seed_tenant["manager"].email in recipients
    assert seed_tenant["admin"].email in recipients
    assert seed_tenant["viewer"].email not in recipients
    assert "grab bar" in sent[0][2]

    staff = _login(client, seed_tenant["manager"].email)
    inbox = client.get("/api/v1/home-safety/care/family-messages", headers=staff)
    assert inbox.status_code == 200, inbox.text
    rows = inbox.json()
    row = next(r for r in rows if r["elder_id"] == elder.id)
    assert row["unread_count"] == 1
    assert row["message_count"] == 1
    assert row["last_message"]["sender_role"] == "family"
    assert row["staff_read_at"] is None

    thread = client.get(f"/api/v1/home-safety/care/family-messages/{elder.id}", headers=staff)
    assert thread.status_code == 200
    assert [m["body"] for m in thread.json()["messages"]] == ["Can someone check the grab bar?"]

    read = client.post(f"/api/v1/home-safety/care/family-messages/{elder.id}/read", headers=staff)
    assert read.status_code == 200
    assert read.json()["unread_count"] == 0
    inbox2 = client.get("/api/v1/home-safety/care/family-messages", headers=staff).json()
    assert next(r for r in inbox2 if r["elder_id"] == elder.id)["unread_count"] == 0


def test_staff_reply_appears_for_family_with_alert(db, client, seed_tenant):
    tenant = seed_tenant["tenant"]
    fam, elder = _family(db, tenant.id, "b")
    fam_headers = _login(client, fam.email)
    client.post("/api/v1/home-safety/family/messages", headers=fam_headers, json={"body": "Hello"})

    staff = _login(client, seed_tenant["manager"].email)
    reply = client.post(
        f"/api/v1/home-safety/care/family-messages/{elder.id}/reply",
        headers=staff,
        json={"body": "We will visit on Friday."},
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["sender_role"] == "team"
    assert reply.json()["sender_name"] == "Test Manager"

    # Replying counts as having read the thread.
    row = next(
        r
        for r in client.get("/api/v1/home-safety/care/family-messages", headers=staff).json()
        if r["elder_id"] == elder.id
    )
    assert row["unread_count"] == 0
    assert row["last_message"]["sender_role"] == "team"

    msgs = client.get("/api/v1/home-safety/family/messages", headers=fam_headers).json()
    assert [m["sender_role"] for m in msgs] == ["family", "team"]
    # The reply shows once in the timeline, as a message from the named sender —
    # not also as a separate "Reply from your care team" notice (Batch B de-dupe).
    feed = client.get("/api/v1/home-safety/family/care-feed", headers=fam_headers).json()
    assert not any(a.get("title") == "Reply from your care team" for a in feed)
    assert any("Test Manager" in f"{a.get('title', '')} {a.get('body', '')} {a.get('sender_name', '')}" for a in feed)

    # A blank reply is refused; a viewer cannot reply at all.
    assert (
        client.post(
            f"/api/v1/home-safety/care/family-messages/{elder.id}/reply",
            headers=staff,
            json={"body": "   "},
        ).status_code
        == 400
    )
    viewer = _login(client, seed_tenant["viewer"].email)
    assert (
        client.post(
            f"/api/v1/home-safety/care/family-messages/{elder.id}/reply",
            headers=viewer,
            json={"body": "hi"},
        ).status_code
        == 403
    )


def test_staff_inbox_is_tenant_scoped(db, client, seed_tenant):
    other = Tenant(name="Other Agency", email="other@test.example", phone="1", address="x", city="y", state="z")
    db.add(other)
    db.flush()
    other_admin = User(
        email="other.admin.inbox@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Other",
        last_name="Admin",
        role="TENANT_ADMIN",
        tenant_id=other.id,
    )
    db.add(other_admin)
    db.flush()
    fam_here, elder_here = _family(db, seed_tenant["tenant"].id, "c")
    fam_there, elder_there = _family(db, other.id, "d")
    for fam in (fam_here, fam_there):
        client.post(
            "/api/v1/home-safety/family/messages",
            headers=_login(client, fam.email),
            json={"body": f"from {fam.email}"},
        )

    here = _login(client, seed_tenant["manager"].email)
    there = _login(client, other_admin.email)
    here_ids = {r["elder_id"] for r in client.get("/api/v1/home-safety/care/family-messages", headers=here).json()}
    there_ids = {r["elder_id"] for r in client.get("/api/v1/home-safety/care/family-messages", headers=there).json()}
    assert elder_here.id in here_ids and elder_there.id not in here_ids
    assert elder_there.id in there_ids and elder_here.id not in there_ids

    # Direct thread / reply / read on the other tenant's client is refused.
    for method, path in (
        ("get", f"/api/v1/home-safety/care/family-messages/{elder_there.id}"),
        ("post", f"/api/v1/home-safety/care/family-messages/{elder_there.id}/read"),
    ):
        res = getattr(client, method)(path, headers=here)
        assert res.status_code in (403, 404), (path, res.status_code)
    res = client.post(
        f"/api/v1/home-safety/care/family-messages/{elder_there.id}/reply",
        headers=here,
        json={"body": "nope"},
    )
    assert res.status_code in (403, 404)
    msgs = client.get("/api/v1/home-safety/family/messages", headers=_login(client, fam_there.email)).json()
    assert all(m["body"] != "nope" for m in msgs)
