"""Email notifications: agency rules, family choices, and who actually gets each email."""

from app.livewell import email_notifications as en


def _admin(client):
    res = client.post("/api/v1/auth/login", json={"email": "admin@test.example", "password": "testpass123"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _capture(monkeypatch):
    sent = []
    monkeypatch.setattr(
        en, "send", lambda to, title, body, *, family, background=True: sent.append((list(to), title, family))
    )
    return sent


def test_agency_rules_and_family_prefs(client, db, seed_tenant, auth_headers, monkeypatch):
    elder = seed_tenant["elder"]
    res = client.get("/api/v1/team/email-notifications", headers=auth_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["staff"]["request"]["enabled"] and data["family"]["visit"]
    assert data["status"]["provider"]

    admin = _admin(client)
    res = client.put(
        "/api/v1/team/email-notifications",
        json={
            "staff": {"request": {"admins": False, "extra": ["desk@kushalaya.example", "bad-address"]}},
            "family": {"visit_live": False},
        },
        headers=admin,
    )
    assert res.status_code == 200, res.text
    assert res.json()["staff"]["request"]["extra"] == ["desk@kushalaya.example"]

    # Family login, then the family's own choices.
    res = client.post(
        f"/api/v1/team/clients/{elder.id}/family-logins",
        json={"email": "son@family.example", "password": "familypass1"},
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    tok = client.post("/api/v1/auth/login", json={"email": "son@family.example", "password": "familypass1"}).json()
    fam = {"Authorization": f"Bearer {tok['access_token']}"}
    prefs = client.get("/api/v1/home-safety/family/email-prefs", headers=fam).json()
    assert prefs["logins"] == ["son@family.example"]
    assert "visit_live" not in {e["key"] for e in prefs["events"]}  # agency turned it off
    prefs = client.put(
        "/api/v1/home-safety/family/email-prefs",
        json={"extra": ["daughter@family.example"], "off": ["reply"]},
        headers=fam,
    ).json()
    assert prefs["extra"] == ["daughter@family.example"] and prefs["off"] == ["reply"]

    db.expire_all()
    assert set(en.family_recipients(db, elder, "visit")) == {"son@family.example", "daughter@family.example"}
    assert en.family_recipients(db, elder, "reply") == []
    assert en.family_recipients(db, elder, "visit_live") == []
    assert "desk@kushalaya.example" in en.staff_recipients(db, elder, "request")

    # A family request emails the staff who follow requests.
    sent = _capture(monkeypatch)
    from app.livewell.family_notify import notify_manager

    notify_manager(db, elder, "New request", "Visit please")
    assert sent and "desk@kushalaya.example" in sent[0][0] and sent[0][2] is False


def test_test_email_and_html(client, auth_headers):
    res = client.post("/api/v1/team/email-notifications/test", json={"to": "me@kushalaya.example"}, headers=_admin(client))
    assert res.status_code == 200, res.text
    page = en.render_html("Visit <b>", "Line one\nLine two", link="https://x.example", link_label="Open")
    assert "Visit &lt;b&gt;" in page and "Line two" in page
