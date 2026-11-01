"""Add demo elder portal user to existing DB. Run: python -m app.seed_elder_portal"""

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.elder import Elder
from app.models.elder_message import DIRECTION_TENANT_TO_ELDER, ElderMessage
from app.models.elder_notification import ElderNotification
from app.models.tenant import Tenant
from app.models.user import User

DEMO_PASSWORD = "demo1234"
PORTAL_EMAIL = "lakshmi.family@sunrise-care.example"


def seed_portal():
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == PORTAL_EMAIL).first():
            print("Elder portal user already exists.")
            return

        tenant = db.query(Tenant).filter(Tenant.name == "Sunrise Elder Care").first()
        if not tenant:
            print("Run seed_db first.")
            return

        elder = (
            db.query(Elder)
            .filter(Elder.tenant_id == tenant.id, Elder.first_name == "Lakshmi")
            .first()
        )
        if not elder:
            print("Demo elder not found.")
            return

        manager = (
            db.query(User)
            .filter(User.email == "manager@sunrise-care.example")
            .first()
        )

        user = User(
            email=PORTAL_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            first_name="Lakshmi",
            last_name="Reddy",
            role="ELDER_PORTAL",
            tenant_id=tenant.id,
            elder_id=elder.id,
            portal_relationship="self",
        )
        db.add(user)
        db.flush()

        db.add(
            ElderNotification(
                tenant_id=tenant.id,
                elder_id=elder.id,
                title="Welcome to your care portal",
                body="View care status and message your care team anytime.",
                sent_by_user_id=manager.id if manager else None,
            )
        )
        if manager:
            db.add(
                ElderMessage(
                    tenant_id=tenant.id,
                    elder_id=elder.id,
                    direction=DIRECTION_TENANT_TO_ELDER,
                    body="Hello — your care team is here if you need anything.",
                    sender_user_id=manager.id,
                )
            )

        db.commit()
        print(f"Elder portal user: {PORTAL_EMAIL} / {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_portal()
