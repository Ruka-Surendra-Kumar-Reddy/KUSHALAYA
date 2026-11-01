"""Ensure platform super admin exists. Run: python -m app.seed_super_admin"""

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User

SUPER_ADMIN_EMAIL = "superadmin@livewellops.com"
LEGACY_EMAILS = (
    "superadmin@eldercareops.com",
    "system@eldercareops.com",
)
DEMO_PASSWORD = "demo1234"


def seed_super_admin():
    db = SessionLocal()
    try:
        current = db.query(User).filter(User.email == SUPER_ADMIN_EMAIL).first()
        if current:
            print(f"Super admin already exists: {SUPER_ADMIN_EMAIL}")
            return

        for legacy_email in LEGACY_EMAILS:
            legacy = db.query(User).filter(User.email == legacy_email).first()
            if legacy:
                legacy.email = SUPER_ADMIN_EMAIL
                if legacy.role != "SYSTEM_ADMIN":
                    legacy.role = "SYSTEM_ADMIN"
                if legacy.tenant_id is not None:
                    legacy.tenant_id = None
                db.commit()
                print(
                    f"Migrated legacy super admin {legacy_email} -> {SUPER_ADMIN_EMAIL} "
                    f"(password unchanged; demo default is {DEMO_PASSWORD})"
                )
                return

        user = User(
            email=SUPER_ADMIN_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            first_name="Platform",
            last_name="Super Admin",
            role="SYSTEM_ADMIN",
            tenant_id=None,
        )
        db.add(user)
        db.commit()
        print(f"Super admin created: {SUPER_ADMIN_EMAIL} / {DEMO_PASSWORD}")
        print("Use /tenants after login to manage agencies.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_super_admin()
