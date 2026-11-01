"""Clients page: create a client with the family's login, reset the password."""


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_create_client_with_family_login_and_reset(client, seed_tenant, auth_headers):
    res = client.post(
        "/api/v1/team/clients",
        json={
            "first_name": "Kamala",
            "last_name": "Rao",
            "phone": "+919000000002",
            "family": {"name": "Ravi Rao", "email": "Ravi.Rao@Example.com", "password": "family123", "relationship": "son"},
        },
        headers=auth_headers,
    )
    assert res.status_code == 201, res.text
    row = res.json()
    assert row["family_logins"][0]["email"] == "ravi.rao@example.com"
    assert row["manager_user_id"] == seed_tenant["manager"].id  # a manager's new client is in their team

    fam = _login(client, "ravi.rao@example.com", "family123")
    assert client.get("/api/v1/home-safety/family/dashboard", headers=fam).status_code == 200

    uid = row["family_logins"][0]["id"]
    assert client.put(f"/api/v1/team/clients/{row['id']}/family-logins/{uid}/password", json={"password": "newpass123"}, headers=auth_headers).status_code == 200
    _login(client, "ravi.rao@example.com", "newpass123")

    listed = client.get("/api/v1/team/clients", headers=auth_headers).json()
    assert any(c["id"] == row["id"] for c in listed)

    dup = client.post(f"/api/v1/team/clients/{row['id']}/family-logins",
                      json={"email": "ravi.rao@example.com", "password": "x1234567"}, headers=auth_headers)
    assert dup.status_code == 409


def test_clients_awaiting_reply_matches_the_dashboard_rule(client, db, seed_tenant, auth_headers):
    """Read but unanswered family message: the Dashboard lists it, so the Clients
    "Needs attention" filter must count the client too (awaiting_reply)."""
    from sqlalchemy.orm.attributes import flag_modified

    elder = seed_tenant["elder"]
    attrs = dict(elder.custom_attributes or {})
    sh = dict(attrs.get("safe_home") or {})
    sh["family_hub"] = {
        "messages": [{"id": "m1", "sender_role": "family", "body": "Any update?", "created_at": "2026-10-01T10:00:00+00:00"}],
        "staff_read_at": "2026-10-02T10:00:00+00:00",
    }
    attrs["safe_home"] = sh
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")
    db.commit()

    rows = client.get("/api/v1/team/clients", headers=auth_headers).json()
    row = next(r for r in rows if r["id"] == elder.id)
    assert row["unread_messages"] == 0
    assert row["awaiting_reply"] is True
