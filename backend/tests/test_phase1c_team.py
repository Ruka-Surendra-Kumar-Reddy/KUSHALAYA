"""Phase 1C — Team & staff accounts: guards, reassign-on-deactivate, password reset."""

import app.models  # noqa: F401

from app.core.security import hash_password
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.user import User
from app.services import auth_service


class _NoClose:
    """The forgot-password task opens and closes its own session; hand it the test one."""

    def __init__(self, db):
        self._db = db

    def __getattr__(self, name):
        return getattr(self._db, name)

    def close(self):
        pass


def _bg_db(monkeypatch, db):
    monkeypatch.setattr("app.api.v1.auth._session_factory", lambda: _NoClose(db))


def _headers(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _add_user(db, tenant_id, email, role, **kw):
    u = User(
        email=email,
        password_hash=hash_password("testpass123"),
        first_name="Extra",
        last_name="Person",
        role=role,
        tenant_id=tenant_id,
        **kw,
    )
    db.add(u)
    db.commit()
    return u


def test_deactivate_and_reactivate_viewer(client, seed_tenant):
    h = _headers(client, "admin@test.example")
    viewer = seed_tenant["viewer"]
    res = client.post(f"/api/v1/users/{viewer.id}/deactivate", headers=h)
    assert res.status_code == 200 and res.json()["status"] == "INACTIVE"
    login = client.post("/api/v1/auth/login", json={"email": viewer.email, "password": "testpass123"})
    assert login.status_code == 400
    res = client.post(f"/api/v1/users/{viewer.id}/reactivate", headers=h)
    assert res.json()["status"] == "ACTIVE"


def test_last_admin_cannot_be_demoted_or_deactivated(db, client, seed_tenant):
    # Only a platform admin can act on a tenant's sole admin (a tenant admin is one themselves).
    _add_user(db, None, "root@test.example", "SYSTEM_ADMIN")
    h = _headers(client, "root@test.example")
    admin = seed_tenant["admin"]
    res = client.patch(f"/api/v1/users/{admin.id}", headers=h, json={"role": "VIEWER"})
    assert res.status_code == 400 and "last admin" in res.json()["detail"]
    res = client.post(f"/api/v1/users/{admin.id}/deactivate", headers=h)
    assert res.status_code == 400 and "last admin" in res.json()["detail"]
    # With a second admin it's allowed.
    _add_user(db, seed_tenant["tenant"].id, "admin2@test.example", "TENANT_ADMIN")
    assert client.patch(f"/api/v1/users/{admin.id}", headers=h, json={"role": "VIEWER"}).status_code == 200


def test_admin_edits_name_and_email_lowercased(client, seed_tenant):
    h = _headers(client, "admin@test.example")
    viewer = seed_tenant["viewer"]
    res = client.patch(
        f"/api/v1/users/{viewer.id}", headers=h,
        json={"first_name": "Vee", "email": "New.Viewer@Test.example"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["first_name"] == "Vee"
    assert res.json()["email"] == "new.viewer@test.example"


def test_manager_cannot_edit_admin_or_change_roles(client, seed_tenant):
    h = _headers(client, "manager@test.example")
    admin = seed_tenant["admin"]
    res = client.patch(f"/api/v1/users/{admin.id}", headers=h, json={"first_name": "Hacked"})
    assert res.status_code == 403
    res = client.post(f"/api/v1/users/{admin.id}/password", headers=h, json={"password": "newpass123"})
    assert res.status_code == 403
    res = client.post(f"/api/v1/users/{admin.id}/deactivate", headers=h)
    assert res.status_code == 403


def test_admin_sets_password(client, seed_tenant):
    h = _headers(client, "admin@test.example")
    viewer = seed_tenant["viewer"]
    res = client.post(f"/api/v1/users/{viewer.id}/password", headers=h, json={"password": "brandnew123"})
    assert res.status_code == 200
    _headers(client, viewer.email, "brandnew123")


def test_forgot_password_always_200_and_token_single_use(db, client, seed_tenant, monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.livewell.email_notifications.send",
        lambda recipients, title, body, family=False, **k: sent.append((recipients, body, family)),
    )
    auth_service._last_reset_sent.clear()
    _bg_db(monkeypatch, db)
    res = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@nowhere.example"})
    assert res.status_code == 200
    assert sent == []
    res = client.post("/api/v1/auth/forgot-password", json={"email": " Viewer@Test.example "})
    assert res.status_code == 200
    assert len(sent) == 1 and "https://ops.kushalaya.com/reset-password?token=" in sent[0][1]
    # Rate-limited: a second request within 60 s sends nothing.
    client.post("/api/v1/auth/forgot-password", json={"email": "viewer@test.example"})
    assert len(sent) == 1

    token = sent[0][1].split("token=")[1].split()[0]
    res = client.post("/api/v1/auth/reset-password", json={"token": token, "password": "resetpass123"})
    assert res.status_code == 200, res.text
    _headers(client, "viewer@test.example", "resetpass123")
    # Single use: the password hash changed, so the same link no longer works.
    res = client.post("/api/v1/auth/reset-password", json={"token": token, "password": "another123"})
    assert res.status_code == 400
    res = client.post("/api/v1/auth/reset-password", json={"token": "garbage-token", "password": "another123"})
    assert res.status_code == 400


def test_forgot_password_family_link_and_inactive_silent(db, client, seed_tenant, monkeypatch):
    sent = []
    monkeypatch.setattr(
        "app.livewell.email_notifications.send",
        lambda recipients, title, body, family=False, **k: sent.append((body, family)),
    )
    auth_service._last_reset_sent.clear()
    _bg_db(monkeypatch, db)
    _add_user(db, seed_tenant["tenant"].id, "fam@test.example", "ELDER_PORTAL", elder_id=seed_tenant["elder"].id)
    _add_user(db, seed_tenant["tenant"].id, "gone@test.example", "VIEWER", status="INACTIVE")
    client.post("/api/v1/auth/forgot-password", json={"email": "gone@test.example"})
    assert sent == []
    client.post("/api/v1/auth/forgot-password", json={"email": "fam@test.example"})
    assert sent[0][1] is True and "https://family.kushalaya.com/reset-password?token=" in sent[0][0]


def test_deactivating_manager_requires_reassign(db, client, seed_tenant):
    h = _headers(client, "admin@test.example")
    old = seed_tenant["manager"]
    new = _add_user(db, seed_tenant["tenant"].id, "manager2@test.example", "CARE_MANAGER")
    res = client.get(f"/api/v1/users/{old.id}/caseload", headers=h)
    assert res.json() == {"clients": 1, "caregivers": 1}
    res = client.post(f"/api/v1/users/{old.id}/deactivate", headers=h)
    assert res.status_code == 400 and "Reassign their 1 clients and 1 caregivers" in res.json()["detail"]
    db.refresh(old)
    assert old.status == "ACTIVE"
    res = client.post(f"/api/v1/users/{old.id}/deactivate", headers=h, json={"reassign_to_manager_id": new.id})
    assert res.status_code == 200 and res.json()["status"] == "INACTIVE"
    db.expire_all()
    assert db.get(Caregiver, seed_tenant["caregiver"].id).manager_user_id == new.id
    assert db.get(Elder, seed_tenant["elder"].id).manager_user_id == new.id


def test_managers_list_has_caseload_counts(client, seed_tenant):
    h = _headers(client, "admin@test.example")
    rows = client.get("/api/v1/team/managers", headers=h).json()
    m = next(r for r in rows if r["id"] == seed_tenant["manager"].id)
    assert m["clients"] == 1 and m["caregivers"] == 1


def test_caregiver_edit_is_team_scoped(db, client, seed_tenant):
    other_mgr = _add_user(db, seed_tenant["tenant"].id, "manager2@test.example", "CARE_MANAGER")
    outsider = Caregiver(tenant_id=seed_tenant["tenant"].id, first_name="Out", last_name="Sider", manager_user_id=other_mgr.id)
    db.add(outsider)
    db.commit()
    h = _headers(client, "manager@test.example")
    mine = seed_tenant["caregiver"]
    res = client.patch(f"/api/v1/team/caregivers/{mine.id}", headers=h, json={"first_name": "Kavya", "phone": "9876543210"})
    assert res.status_code == 200, res.text
    assert res.json()["first_name"] == "Kavya" and res.json()["phone"] == "9876543210"
    res = client.patch(f"/api/v1/team/caregivers/{outsider.id}", headers=h, json={"first_name": "X"})
    assert res.status_code == 404
    # Mark as left switches off their login too.
    login = _add_user(db, seed_tenant["tenant"].id, "cg@test.example", "CAREGIVER", caregiver_id=mine.id)
    res = client.patch(f"/api/v1/team/caregivers/{mine.id}", headers=h, json={"status": "INACTIVE"})
    assert res.status_code == 200 and res.json()["status"] == "INACTIVE"
    db.refresh(login)
    assert login.status == "INACTIVE"


def test_manager_creates_caregiver_in_own_team(client, seed_tenant):
    h = _headers(client, "manager@test.example")
    res = client.post(
        "/api/v1/team/caregivers", headers=h,
        json={"first_name": "New", "manager_user_id": seed_tenant["admin"].id},
    )
    assert res.status_code == 201, res.text
    assert res.json()["manager_user_id"] == seed_tenant["manager"].id
    h_viewer = _headers(client, "viewer@test.example")
    assert client.post("/api/v1/team/caregivers", headers=h_viewer, json={"first_name": "No"}).status_code == 403


def test_invite_rejects_family_without_elder_and_lowercases(client, seed_tenant):
    h = _headers(client, "admin@test.example")
    tid = seed_tenant["tenant"].id
    base = {"password": "invitepass1", "first_name": "A", "last_name": "B", "tenant_id": tid}
    res = client.post("/api/v1/users/invite", headers=h, json={**base, "email": "fam2@test.example", "role": "ELDER_PORTAL"})
    assert res.status_code == 400
    res = client.post("/api/v1/users/invite", headers=h, json={**base, "email": "New.Manager@Test.example", "role": "CARE_MANAGER"})
    assert res.status_code == 200, res.text
    assert res.json()["email"] == "new.manager@test.example"
    res = client.post("/api/v1/users/invite", headers=h, json={**base, "email": "NEW.manager@test.example", "role": "VIEWER"})
    assert res.status_code == 409


# --- audit fixes -------------------------------------------------------------

from jose import jwt as _jwt  # noqa: E402

from app.core.security import ALGORITHM, SECRET_KEY  # noqa: E402
from app.models.audit_log import AuditLog  # noqa: E402


def _token(client, email, password="testpass123"):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()


def _me(client, access):
    return client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"}).status_code


def test_manager_cannot_reactivate_caregiver_or_login(db, client, seed_tenant):
    cg = seed_tenant["caregiver"]
    login = _add_user(db, seed_tenant["tenant"].id, "cg@test.example", "CAREGIVER", caregiver_id=cg.id)
    admin_h = _headers(client, "admin@test.example")
    mgr_h = _headers(client, "manager@test.example")
    # Admin switched off the login only; a manager's plain edit must not switch it back on.
    client.post(f"/api/v1/users/{login.id}/deactivate", headers=admin_h)
    res = client.patch(f"/api/v1/team/caregivers/{cg.id}", headers=mgr_h, json={"status": "ACTIVE"})
    assert res.status_code == 200
    db.refresh(login)
    assert login.status == "INACTIVE"
    # Marked as left: only an admin can bring them back.
    assert client.patch(f"/api/v1/team/caregivers/{cg.id}", headers=mgr_h, json={"status": "INACTIVE"}).status_code == 200
    assert client.patch(f"/api/v1/team/caregivers/{cg.id}", headers=mgr_h, json={"status": "ACTIVE"}).status_code == 403
    assert client.put(f"/api/v1/caregivers/{cg.id}", headers=mgr_h, json={"status": "ACTIVE"}).status_code == 403
    assert client.patch(f"/api/v1/team/caregivers/{cg.id}", headers=mgr_h, json={"status": "BOGUS"}).status_code == 400
    res = client.patch(f"/api/v1/team/caregivers/{cg.id}", headers=admin_h, json={"status": "ACTIVE"})
    assert res.status_code == 200
    db.refresh(login)
    assert login.status == "ACTIVE"


def test_caregiver_email_kept_in_step_and_delete_disables_login(db, client, seed_tenant):
    cg = seed_tenant["caregiver"]
    login = _add_user(db, seed_tenant["tenant"].id, "cg@test.example", "CAREGIVER", caregiver_id=cg.id)
    h = _headers(client, "manager@test.example")
    assert client.patch(f"/api/v1/team/caregivers/{cg.id}", headers=h, json={"email": None}).status_code == 400
    res = client.put(f"/api/v1/caregivers/{cg.id}", headers=h, json={"email": "Moved@Test.example"})
    assert res.status_code == 200, res.text
    db.refresh(login)
    assert login.email == "moved@test.example"
    assert client.delete(f"/api/v1/caregivers/{cg.id}", headers=h).status_code == 200
    db.refresh(login)
    assert login.status == "INACTIVE"


def test_audit_rows_for_caregiver_and_user_changes(db, client, seed_tenant):
    h = _headers(client, "admin@test.example")
    cg = seed_tenant["caregiver"]
    client.patch(f"/api/v1/team/caregivers/{cg.id}", headers=h, json={"phone": "9000000000"})
    client.post("/api/v1/team/caregivers", headers=h, json={"first_name": "Audit"})
    viewer = seed_tenant["viewer"]
    client.post(f"/api/v1/users/{viewer.id}/password", headers=h, json={"password": "auditpass1"})
    client.patch(f"/api/v1/users/{viewer.id}", headers=h, json={"email": "aud@test.example"})
    actions = {a for (a,) in db.query(AuditLog.action).all()}
    assert {"caregiver_updated", "caregiver_created", "user_password_reset", "user_updated"} <= actions
    row = db.query(AuditLog).filter(AuditLog.action == "caregiver_updated").first()
    assert row.old_value["phone"] != row.new_value["phone"] == "9000000000"
    pw = db.query(AuditLog).filter(AuditLog.action == "user_password_reset").first()
    assert "auditpass1" not in str(pw.new_value) and "password" not in str(pw.new_value)


def test_uid_mismatch_is_rejected(client, seed_tenant):
    access = _token(client, "viewer@test.example")["access_token"]
    assert _me(client, access) == 200
    payload = _jwt.decode(access, SECRET_KEY, algorithms=[ALGORITHM])
    payload["uid"] = 999999
    assert _me(client, _jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)) == 401
    # Tokens issued before the claims existed keep working.
    payload.pop("uid")
    payload.pop("pwv")
    assert _me(client, _jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)) == 200


def test_password_change_invalidates_old_tokens(client, seed_tenant):
    old = _token(client, "viewer@test.example")
    h = _headers(client, "admin@test.example")
    client.post(f"/api/v1/users/{seed_tenant['viewer'].id}/password", headers=h, json={"password": "rotated123"})
    assert _me(client, old["access_token"]) == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]}).status_code == 400
    # Changing your own password keeps you signed in on the fresh tokens it returns.
    mine = _token(client, "viewer@test.example", "rotated123")
    res = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {mine['access_token']}"},
        json={"current_password": "rotated123", "new_password": "rotated456"},
    )
    assert res.status_code == 200
    assert _me(client, mine["access_token"]) == 401
    assert _me(client, res.json()["access_token"]) == 200


def test_email_reuse_cannot_use_old_tokens(db, client, seed_tenant):
    old = _token(client, "viewer@test.example")
    h = _headers(client, "admin@test.example")
    viewer = seed_tenant["viewer"]
    assert client.patch(f"/api/v1/users/{viewer.id}", headers=h, json={"email": "renamed@test.example"}).status_code == 200
    _add_user(db, seed_tenant["tenant"].id, "viewer@test.example", "VIEWER")
    assert _me(client, old["access_token"]) == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]}).status_code == 400
