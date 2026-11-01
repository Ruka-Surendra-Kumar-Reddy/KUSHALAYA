"""Zoho SMTP / MSG91 set from Settings: secrets are encrypted and never returned."""

from app.services.notifications import channel_config as cc


def _admin(client):
    res = client.post("/api/v1/auth/login", json={"email": "admin@test.example", "password": "testpass123"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_save_email_and_sms_channels(client, db, seed_tenant, auth_headers, monkeypatch):
    admin = _admin(client)
    assert client.get("/api/v1/team/channels", headers=auth_headers).status_code == 403  # managers can't

    res = client.put(
        "/api/v1/team/channels/email",
        json={"host": "smtp.zoho.in", "port": 587, "username": "care@kushalaya.com",
              "password": "abcd efgh ijkl", "from_name": "KushAlaya", "enabled": True},
        headers=admin,
    )
    assert res.status_code == 200, res.text
    view = res.json()
    assert view["secret_set"] and view["enabled"] and "password" not in view and "secret" not in view
    assert "abcd" not in res.text

    raw = cc._read_raw("email", db)
    assert raw["secret"] != "abcdefghijkl" and cc._decrypt(raw["secret"]) == "abcdefghijkl"

    # The providers read through active(); point it at the test database.
    orig = cc._read_raw
    monkeypatch.setattr(cc, "_read_raw", lambda kind, db_=None: orig(kind, db))
    cc.clear_cache()
    cfg = cc.active("email")
    assert cfg["password"] == "abcdefghijkl" and cfg["username"] == "care@kushalaya.com"
    from app.services.notifications.factory import get_email_provider
    from app.services.notifications.smtp_email import SmtpEmailProvider

    assert isinstance(get_email_provider(), SmtpEmailProvider)

    # Saving again without a password keeps the old one.
    client.put("/api/v1/team/channels/email", json={"from_name": "Kushalaya Care"}, headers=admin)
    cc.clear_cache()
    assert cc.active("email")["password"] == "abcdefghijkl"

    bad = client.put("/api/v1/team/channels/sms", json={"sender_id": "TOOLONGID"}, headers=admin)
    assert bad.status_code == 400
    ok = client.put("/api/v1/team/channels/sms", json={"sender_id": "KUSHAL", "auth_key": "k-123", "enabled": True},
                    headers=admin)
    assert ok.status_code == 200 and ok.json()["secret_set"] and "k-123" not in ok.text

    # Turned off -> back to .env providers.
    client.put("/api/v1/team/channels/email", json={"enabled": False}, headers=admin)
    cc.clear_cache()
    assert cc.active("email") is None
    cc.clear_cache()


def test_channel_status_is_readable_by_managers_without_secrets(client, db, seed_tenant, auth_headers, monkeypatch):
    """Dashboard / Alerts "SOS SMS are OFF" banner: every staff role may read connected yes/no."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "NOTIFICATION_SMS_PROVIDER", "log")
    res = client.get("/api/v1/team/channels/status", headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json() == {"sms_connected": False, "email_connected": res.json()["email_connected"]}
    assert "secret" not in res.text and "sender" not in res.text

    admin = _admin(client)
    client.put(
        "/api/v1/team/channels/sms",
        json={"auth_key": "k" * 24, "sender_id": "KUSHAL", "template_id": "t1", "enabled": True},
        headers=admin,
    )
    on = client.get("/api/v1/team/channels/status", headers=auth_headers).json()
    assert on["sms_connected"] is True
