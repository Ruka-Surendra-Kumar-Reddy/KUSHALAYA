"""Add elder + family portal user at 2450 Clairview St, Alpharetta GA 30009.

Run: python -m app.db_migrate && python -m app.seed_clairview_demo
"""

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.assignment import Assignment
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.elder_location import ElderLocation
from app.models.elder_notification import ElderNotification
from app.models.tenant import Tenant
from app.models.user import User

# Geocoded via OpenStreetMap (2450 Clairview St, Alpharetta, GA 30009)
CLAIRVIEW_LAT = 34.0781034
CLAIRVIEW_LON = -84.2829513
GEOFENCE_RADIUS_M = 100.0

ELDER_FIRST = "Padmaja"
ELDER_LAST = "Posa"
ELDER_ADDRESS = "2450 Clairview St, Alpharetta, GA 30009, USA"
FAMILY_EMAIL = "clairview.family@sunrise-care.example"
DEMO_PASSWORD = "demo1234"


def seed():
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == FAMILY_EMAIL).first():
            print(f"Already exists: {FAMILY_EMAIL}")
            elder = (
                db.query(Elder)
                .filter(
                    Elder.address == ELDER_ADDRESS,
                )
                .first()
            )
            if elder:
                print(f"  Elder id={elder.id} — {elder.first_name} {elder.last_name}")
            return

        tenant = db.query(Tenant).filter(Tenant.name == "Sunrise Elder Care").first()
        if not tenant:
            print("Sunrise Elder Care tenant not found. Run: python -m app.seed_db")
            return

        elder = Elder(
            tenant_id=tenant.id,
            first_name=ELDER_FIRST,
            last_name=ELDER_LAST,
            phone="+1-404-555-2450",
            address=ELDER_ADDRESS,
            emergency_contact_name="Srikrishna Posa",
            emergency_contact_phone="+1-404-555-2450",
            care_level="Medium",
            mobility_status="Independent",
            custom_attributes={
                "language_preference": "English",
                "latitude": CLAIRVIEW_LAT,
                "longitude": CLAIRVIEW_LON,
                "geofence_radius_meters": GEOFENCE_RADIUS_M,
                "care_type": "visit_based",
                "schedule_requirements": {"days": ["mon", "wed", "fri"]},
            },
        )
        db.add(elder)
        db.flush()

        db.add(
            ElderLocation(
                tenant_id=tenant.id,
                elder_id=elder.id,
                latitude=CLAIRVIEW_LAT,
                longitude=CLAIRVIEW_LON,
                radius_meters=GEOFENCE_RADIUS_M,
            )
        )

        manager = (
            db.query(User)
            .filter(User.email == "manager@sunrise-care.example")
            .first()
        )

        db.add(
            User(
                email=FAMILY_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                first_name=ELDER_FIRST,
                last_name=ELDER_LAST,
                role="ELDER_PORTAL",
                tenant_id=tenant.id,
                elder_id=elder.id,
                portal_relationship="self",
            )
        )

        caregiver = (
            db.query(Caregiver)
            .filter(Caregiver.tenant_id == tenant.id)
            .order_by(Caregiver.id)
            .first()
        )
        if caregiver:
            existing = (
                db.query(Assignment)
                .filter(
                    Assignment.elder_id == elder.id,
                    Assignment.caregiver_id == caregiver.id,
                )
                .first()
            )
            if not existing:
                db.add(
                    Assignment(
                        tenant_id=tenant.id,
                        elder_id=elder.id,
                        caregiver_id=caregiver.id,
                        status="ACTIVE",
                        match_score=88.0,
                    )
                )

        if manager:
            db.add(
                ElderNotification(
                    tenant_id=tenant.id,
                    elder_id=elder.id,
                    title="Welcome to your care portal",
                    body=(
                        "Your home at Clairview St is set up for visit check-in. "
                        "Contact Sunrise Elder Care anytime from Contact."
                    ),
                    sent_by_user_id=manager.id,
                )
            )

        db.commit()
        print("Clairview demo created.")
        print(f"  Elder: {ELDER_FIRST} {ELDER_LAST} (id={elder.id})")
        print(f"  Address: {ELDER_ADDRESS}")
        print(f"  Geofence: {CLAIRVIEW_LAT}, {CLAIRVIEW_LON} ({GEOFENCE_RADIUS_M}m)")
        print(f"  Family portal: {FAMILY_EMAIL} / {DEMO_PASSWORD}")
        if caregiver:
            print(
                f"  Assigned caregiver: {caregiver.first_name} {caregiver.last_name} "
                f"(id={caregiver.id}) — use PWA at the home for real GPS check-in"
            )
    finally:
        db.close()


if __name__ == "__main__":
    seed()
