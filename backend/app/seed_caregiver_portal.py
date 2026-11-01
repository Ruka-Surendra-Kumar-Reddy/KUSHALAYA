"""Add demo caregiver portal user + assignment + geofence on existing seed DB.

Run: python -m app.db_migrate && python -m app.seed_caregiver_portal
"""

from datetime import date

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.assignment import Assignment
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.elder_location import ElderLocation
from app.models.tenant import Tenant
from app.models.user import User

DEMO_EMAIL = "anita.caregiver@sunrise-care.example"
DEMO_PASSWORD = "demo1234"


def seed():
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == DEMO_EMAIL).first():
            print("Caregiver portal demo user already exists. Skipping.")
            return

        tenant = db.query(Tenant).filter(Tenant.name == "Sunrise Elder Care").first()
        if not tenant:
            print("Sunrise Elder Care tenant not found. Run seed_db first.")
            return

        elder = db.query(Elder).filter(Elder.tenant_id == tenant.id).first()
        caregiver = db.query(Caregiver).filter(Caregiver.tenant_id == tenant.id).first()
        if not elder or not caregiver:
            print("Need at least one elder and caregiver in tenant.")
            return

        if not db.query(Assignment).filter(
            Assignment.caregiver_id == caregiver.id,
            Assignment.elder_id == elder.id,
            Assignment.status == "ACTIVE",
        ).first():
            db.add(
                Assignment(
                    tenant_id=tenant.id,
                    elder_id=elder.id,
                    caregiver_id=caregiver.id,
                    status="ACTIVE",
                    match_score=90.0,
                )
            )

        if not db.query(ElderLocation).filter(ElderLocation.elder_id == elder.id).first():
            attrs = elder.custom_attributes or {}
            lat = float(attrs.get("latitude") or 17.4239)
            lon = float(attrs.get("longitude") or 78.4738)
            db.add(
                ElderLocation(
                    tenant_id=tenant.id,
                    elder_id=elder.id,
                    latitude=lat,
                    longitude=lon,
                    radius_meters=100.0,
                )
            )

        db.add(
            User(
                email=DEMO_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                first_name=caregiver.first_name,
                last_name=caregiver.last_name,
                role="CAREGIVER",
                tenant_id=tenant.id,
                caregiver_id=caregiver.id,
            )
        )
        db.commit()
        print(f"Caregiver portal: {DEMO_EMAIL} / {DEMO_PASSWORD}")
        print(f"  Linked caregiver id={caregiver.id}, elder id={elder.id}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
