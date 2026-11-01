"""Tenant hard-delete (pilot cleanup)."""

from app.core.security import hash_password
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.tenant import Tenant
from app.models.user import User
from app.models.tenant import Tenant as TenantModel
from app.services.tenant_purge_service import PROTECTED_TENANT_NAMES, TenantPurgeService


def _super_admin_headers(client, db):
    user = User(
        email="purge-super@test.example",
        password_hash=hash_password("testpass123"),
        first_name="Super",
        last_name="Admin",
        role="SYSTEM_ADMIN",
        tenant_id=None,
    )
    db.add(user)
    db.commit()
    r = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "testpass123"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_delete_tenant_requires_confirm_name(db, client, seed_tenant):
    tenant_id = seed_tenant["tenant"].id
    headers = _super_admin_headers(client, db)

    r = client.request(
        "DELETE",
        f"/api/v1/tenants/{tenant_id}",
        headers=headers,
        json={"confirm_name": "Wrong Name"},
    )
    assert r.status_code == 400

    assert db.query(TenantModel).filter(TenantModel.id == tenant_id).first()


def test_delete_tenant_removes_data(db, client, seed_tenant):
    tenant = seed_tenant["tenant"]
    tenant_id = tenant.id
    headers = _super_admin_headers(client, db)

    r = client.request(
        "DELETE",
        f"/api/v1/tenants/{tenant_id}",
        headers=headers,
        json={"confirm_name": tenant.name},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["tenant_id"] == tenant_id
    assert body["tenant_name"] == tenant.name
    assert body["deleted_counts"].get("users", 0) >= 1

    assert db.query(Tenant).filter(Tenant.id == tenant_id).first() is None
    assert db.query(User).filter(User.tenant_id == tenant_id).count() == 0
    assert db.query(Elder).filter(Elder.tenant_id == tenant_id).count() == 0
    assert (
        db.query(Caregiver).filter(Caregiver.tenant_id == tenant_id).count() == 0
    )


def test_protected_tenant_cannot_be_deleted(db, client, seed_tenant):
    protected_name = next(iter(PROTECTED_TENANT_NAMES))
    tenant = Tenant(
        name=protected_name,
        email="protected@test.example",
        phone="+1",
        address="x",
        city="y",
        state="z",
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    headers = _super_admin_headers(client, db)

    r = client.request(
        "DELETE",
        f"/api/v1/tenants/{tenant.id}",
        headers=headers,
        json={"confirm_name": protected_name},
    )
    assert r.status_code == 400
    assert db.query(Tenant).filter(Tenant.id == tenant.id).first()
