"""Tenant admin user management: role changes, deactivate / reactivate."""

import app.models  # noqa: F401

from app.models.audit_log import AuditLog
from app.models.user import User


def _login(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return res


def _headers(client, email):
    res = _login(client, email)
    assert res.status_code == 200, res.text
    body = res.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body


def test_admin_changes_role_and_it_is_audited(db, client, seed_tenant):
    headers, _ = _headers(client, "admin@test.example")
    viewer = seed_tenant["viewer"]

    res = client.patch(f"/api/v1/users/{viewer.id}", headers=headers, json={"role": "CARE_MANAGER"})
    assert res.status_code == 200, res.text
    assert res.json()["role"] == "CARE_MANAGER"
    assert res.json()["status"] == "ACTIVE"

    db.refresh(viewer)
    assert viewer.role == "CARE_MANAGER"
    row = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "user", AuditLog.action == "user_role_changed")
        .one()
    )
    assert row.entity_id == viewer.id
    assert row.old_value["role"] == "VIEWER"
    assert row.new_value["role"] == "CARE_MANAGER"


def test_admin_cannot_change_own_role(client, seed_tenant):
    headers, me = _headers(client, "admin@test.example")
    admin = seed_tenant["admin"]
    res = client.patch(f"/api/v1/users/{admin.id}", headers=headers, json={"role": "VIEWER"})
    assert res.status_code == 400
    assert "own role" in res.json()["detail"]


def test_role_must_be_tenant_assignable(client, seed_tenant):
    headers, _ = _headers(client, "admin@test.example")
    viewer = seed_tenant["viewer"]
    for bad in ("SYSTEM_ADMIN", "ELDER_PORTAL", "CAREGIVER", "OWNER"):
        res = client.patch(f"/api/v1/users/{viewer.id}", headers=headers, json={"role": bad})
        assert res.status_code == 400, bad


def test_manager_cannot_manage_users(client, seed_tenant):
    headers, _ = _headers(client, "manager@test.example")
    viewer = seed_tenant["viewer"]
    assert client.patch(f"/api/v1/users/{viewer.id}", headers=headers, json={"role": "VIEWER"}).status_code == 403
    assert client.post(f"/api/v1/users/{viewer.id}/deactivate", headers=headers).status_code == 403


def test_admin_cannot_manage_other_tenants_users(db, client, seed_tenant):
    from app.models.tenant import Tenant

    other = Tenant(
        name="Other Agency",
        email="other@test.example",
        phone="1",
        address="x",
        city="y",
        state="z",
        theme="classic",
        portal_title="Other",
    )
    db.add(other)
    db.flush()
    from app.core.security import hash_password

    stranger = User(
        email="stranger@test.example",
        password_hash=hash_password("testpass123"),
        first_name="S",
        last_name="T",
        role="VIEWER",
        tenant_id=other.id,
    )
    db.add(stranger)
    db.commit()

    headers, _ = _headers(client, "admin@test.example")
    assert client.patch(f"/api/v1/users/{stranger.id}", headers=headers, json={"role": "CARE_MANAGER"}).status_code == 403
    assert client.post(f"/api/v1/users/{stranger.id}/deactivate", headers=headers).status_code == 403


def test_deactivate_blocks_login_refresh_and_tokens_then_reactivate(db, client, seed_tenant):
    admin_headers, _ = _headers(client, "admin@test.example")
    viewer = seed_tenant["viewer"]

    # Viewer signs in before deactivation and keeps their tokens.
    viewer_headers, viewer_login = _headers(client, "viewer@test.example")
    assert client.get("/api/v1/auth/me", headers=viewer_headers).status_code == 200

    res = client.post(f"/api/v1/users/{viewer.id}/deactivate", headers=admin_headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "INACTIVE"

    # Existing access token is rejected immediately.
    assert client.get("/api/v1/auth/me", headers=viewer_headers).status_code == 401
    # Refresh is rejected.
    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": viewer_login["refresh_token"]})
    assert refresh.status_code == 400
    # New login is rejected.
    assert _login(client, "viewer@test.example").status_code == 400

    # Listing still shows the user with their status.
    listed = client.get("/api/v1/users", headers=admin_headers).json()
    assert next(u for u in listed if u["id"] == viewer.id)["status"] == "INACTIVE"

    audit = (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "user", AuditLog.action == "user_deactivated")
        .one()
    )
    assert audit.entity_id == viewer.id
    assert audit.old_value["status"] == "ACTIVE"
    assert audit.new_value["status"] == "INACTIVE"

    res = client.post(f"/api/v1/users/{viewer.id}/reactivate", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "ACTIVE"
    assert _login(client, "viewer@test.example").status_code == 200
    assert (
        db.query(AuditLog)
        .filter(AuditLog.entity_type == "user", AuditLog.action == "user_reactivated")
        .count()
        == 1
    )


def test_admin_cannot_deactivate_self(client, seed_tenant):
    headers, _ = _headers(client, "admin@test.example")
    res = client.post(f"/api/v1/users/{seed_tenant['admin'].id}/deactivate", headers=headers)
    assert res.status_code == 400


def test_invite_requires_min_8_char_password(client, seed_tenant):
    headers, _ = _headers(client, "admin@test.example")
    res = client.post(
        "/api/v1/users/invite",
        headers=headers,
        json={
            "email": "short.pw@test.example",
            "password": "short1",
            "first_name": "S",
            "last_name": "P",
            "tenant_id": seed_tenant["tenant"].id,
            "role": "VIEWER",
        },
    )
    assert res.status_code == 422
