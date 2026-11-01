"""Brute-force protection on sign-in and password-reset requests."""

from datetime import timedelta

from app.services import login_throttle

LOGIN = "/api/v1/auth/login"
FORGOT = "/api/v1/auth/forgot-password"
MSG = "Too many sign-in attempts. Try again in 15 minutes, or reset your password."


def _login(client, email, password="wrong-password", headers=None):
    return client.post(LOGIN, json={"email": email, "password": password}, headers=headers or {})


def test_five_failures_lock_that_email(client, seed_tenant):
    for _ in range(5):
        assert _login(client, "admin@test.example").status_code == 400
    res = _login(client, "admin@test.example")
    assert res.status_code == 429
    assert res.json()["detail"] == MSG
    assert 0 < int(res.headers["Retry-After"]) <= 900
    # Even the right password is refused while locked.
    assert _login(client, "admin@test.example", "testpass123").status_code == 429
    # Case/whitespace variants are the same account.
    assert _login(client, " Admin@Test.Example ").status_code == 429
    # Another account is unaffected.
    assert _login(client, "manager@test.example", "testpass123").status_code == 200


def test_unknown_email_behaves_the_same(client, seed_tenant):
    for _ in range(5):
        res = _login(client, "nobody@nowhere.example")
        assert res.status_code == 400
        assert res.json()["detail"] == "Invalid credentials"
    res = _login(client, "nobody@nowhere.example")
    assert res.status_code == 429
    assert res.json()["detail"] == MSG


def test_success_resets_counter(client, seed_tenant):
    for _ in range(4):
        assert _login(client, "admin@test.example").status_code == 400
    assert _login(client, "admin@test.example", "testpass123").status_code == 200
    for _ in range(4):
        assert _login(client, "admin@test.example").status_code == 400
    assert _login(client, "admin@test.example", "testpass123").status_code == 200


def test_lock_expires_after_15_minutes(client, seed_tenant, monkeypatch):
    for _ in range(5):
        _login(client, "admin@test.example")
    assert _login(client, "admin@test.example", "testpass123").status_code == 429
    real_now = login_throttle._now
    monkeypatch.setattr(login_throttle, "_now", lambda: real_now() + timedelta(minutes=16))
    assert _login(client, "admin@test.example", "testpass123").status_code == 200


def test_ip_limit(client, seed_tenant):
    # 30 failures spread over many emails (none reaches the per-email limit).
    for i in range(30):
        assert _login(client, f"spray{i // 3}@x.example").status_code == 400
    res = _login(client, "manager@test.example", "testpass123")
    assert res.status_code == 429
    assert "Retry-After" in res.headers


def test_ip_from_local_proxy_only(client, seed_tenant, monkeypatch):
    class _Req:
        def __init__(self, peer, headers):
            self.client = type("C", (), {"host": peer})()
            self.headers = headers

    hdrs = {"x-real-ip": "203.0.113.9", "x-forwarded-for": "1.2.3.4, 203.0.113.9"}
    assert login_throttle.client_ip(_Req("127.0.0.1", hdrs)) == "203.0.113.9"
    assert login_throttle.client_ip(_Req("127.0.0.1", {"x-forwarded-for": "1.2.3.4, 203.0.113.9"})) == "203.0.113.9"
    # A direct (non-proxy) client cannot spoof its address.
    assert login_throttle.client_ip(_Req("198.51.100.7", hdrs)) == "198.51.100.7"


def test_forgot_password_limited_per_email(client, seed_tenant, monkeypatch):
    # Don't actually build tokens / send email in this test.
    monkeypatch.setattr("app.api.v1.auth._send_reset_in_background", lambda email: None)
    for _ in range(5):
        assert client.post(FORGOT, json={"email": "admin@test.example"}).status_code == 200
    res = client.post(FORGOT, json={"email": "admin@test.example"})
    assert res.status_code == 429
    assert "Retry-After" in res.headers
    # Unknown address: same behaviour.
    for _ in range(5):
        assert client.post(FORGOT, json={"email": "ghost@x.example"}).status_code == 200
    assert client.post(FORGOT, json={"email": "ghost@x.example"}).status_code == 429
    # Other addresses unaffected.
    assert client.post(FORGOT, json={"email": "manager@test.example"}).status_code == 200
