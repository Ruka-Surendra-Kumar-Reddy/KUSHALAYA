"""LiveWell360™ tenant + tenant admin bootstrap.

Run: python -m app.seed_safehome_admin

Creates (idempotent):
  - Tenant: LiveWell Demo (vertical LIVEWELL360)
  - Tenant admin: admin@sunrise-care.example / demo1234
"""

from __future__ import annotations

from app.livewell.brand import brand_name
from app.core.database import SessionLocal
from app.core.security import hash_password, verify_password
from app.models.tenant import Tenant
from app.models.user import User
from app.seed_safehome_constants import (
    CONTACT_EMAIL,
    DEMO_PASSWORD,
    LEGACY_ADMIN_EMAIL,
    LEGACY_TENANT_NAMES,
    TENANT_ADMIN_EMAIL,
    TENANT_NAME,
)


def resolve_safehome_tenant(db) -> Tenant | None:
    tenant = db.query(Tenant).filter(Tenant.name == TENANT_NAME).first()
    if tenant:
        return tenant
    for legacy_name in LEGACY_TENANT_NAMES:
        tenant = db.query(Tenant).filter(Tenant.name == legacy_name).first()
        if tenant:
            return tenant
    tenant = (
        db.query(Tenant)
        .filter(Tenant.vertical == "LIVEWELL360")
        .order_by(Tenant.id)
        .first()
    )
    if tenant:
        return tenant
    return db.query(Tenant).order_by(Tenant.id).first()


def ensure_safehome_tenant(db) -> Tenant:
    tenant = resolve_safehome_tenant(db)
    if tenant:
        changed = False
        if tenant.vertical != "LIVEWELL360":
            tenant.vertical = "LIVEWELL360"
            changed = True
        if tenant.name in LEGACY_TENANT_NAMES:
            tenant.name = TENANT_NAME
            changed = True
        if not tenant.register_slug:
            tenant.register_slug = "safehome-demo"
            changed = True
        if (
            not tenant.portal_title
            or tenant.portal_title == tenant.name
            or tenant.portal_title in ("LiveWell360™", "LiveWell360", "SafeHome 360™")
        ):
            tenant.portal_title = brand_name()
            changed = True
        if changed:
            db.flush()
            print(f"Updated tenant for SafeHomeOps: {tenant.name} (id={tenant.id})")
        return tenant

    tenant = Tenant(
        name=TENANT_NAME,
        register_slug="safehome-demo",
        email=CONTACT_EMAIL,
        phone="+91-9876543210",
        address="12 MG Road",
        city="Hyderabad",
        state="Telangana",
        vertical="LIVEWELL360",
        theme="classic",
        portal_title=brand_name(),
    )
    db.add(tenant)
    db.flush()
    print(f"Created SafeHome tenant: {TENANT_NAME} (id={tenant.id})")
    return tenant


def _remove_legacy_admin(db) -> None:
    legacy = db.query(User).filter(User.email == LEGACY_ADMIN_EMAIL).first()
    if legacy:
        db.delete(legacy)
        print(f"Removed legacy duplicate admin: {LEGACY_ADMIN_EMAIL}")


def _ensure_password(user: User, demo_hash: str) -> bool:
    try:
        if verify_password(DEMO_PASSWORD, user.password_hash):
            return False
    except Exception:
        pass
    user.password_hash = demo_hash
    return True


def ensure_tenant_admin() -> Tenant:
    db = SessionLocal()
    try:
        tenant = ensure_safehome_tenant(db)
        _remove_legacy_admin(db)

        existing = db.query(User).filter(User.email == TENANT_ADMIN_EMAIL).first()
        demo_hash = hash_password(DEMO_PASSWORD)
        if existing:
            changed = False
            if existing.role != "TENANT_ADMIN":
                existing.role = "TENANT_ADMIN"
                changed = True
            if existing.tenant_id != tenant.id:
                existing.tenant_id = tenant.id
                changed = True
            if existing.status != "ACTIVE":
                existing.status = "ACTIVE"
                changed = True
            if _ensure_password(existing, demo_hash):
                changed = True
            db.commit()
            if changed:
                print(f"Tenant admin updated: {TENANT_ADMIN_EMAIL} -> {tenant.name}")
            else:
                print(f"Tenant admin already exists: {TENANT_ADMIN_EMAIL}")
            return tenant

        db.add(
            User(
                email=TENANT_ADMIN_EMAIL,
                password_hash=demo_hash,
                first_name="Priya",
                last_name="Sharma",
                role="TENANT_ADMIN",
                tenant_id=tenant.id,
                status="ACTIVE",
            )
        )
        db.commit()
        print(f"Tenant admin created: {TENANT_ADMIN_EMAIL} / {DEMO_PASSWORD}")
        print(f"  tenant: {tenant.name} (id={tenant.id})")
        return tenant
    finally:
        db.close()


def ensure_care_admin() -> None:
    """Alias for deploy scripts that still call seed_care_admin."""
    ensure_tenant_admin()


if __name__ == "__main__":
    ensure_tenant_admin()
