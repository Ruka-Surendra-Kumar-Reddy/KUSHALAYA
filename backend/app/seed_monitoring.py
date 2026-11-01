"""Add demo monitoring data to existing DB. Run: python -m app.seed_monitoring"""

from datetime import datetime, timedelta

from app.core.database import SessionLocal
from app.models.camera_event import CameraEvent
from app.models.elder import Elder
from app.models.incident import Incident
from app.models.monitoring_consent import MonitoringConsent
from app.models.tenant import Tenant
from app.core.monitoring_config import DEFAULT_MONITORING_CONFIG


def seed_monitoring():
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.name == "Sunrise Elder Care").first()
        if not tenant:
            print("Run app.seed_db first.")
            return
        elder = db.query(Elder).filter(Elder.tenant_id == tenant.id).first()
        if not elder:
            print("No elder found.")
            return
        if db.query(CameraEvent).filter(CameraEvent.tenant_id == tenant.id).first():
            print("Monitoring data already exists. Skipping.")
            return

        if not tenant.monitoring_config:
            tenant.monitoring_config = DEFAULT_MONITORING_CONFIG

        consent = (
            db.query(MonitoringConsent)
            .filter(MonitoringConsent.elder_id == elder.id)
            .first()
        )
        if not consent:
            db.add(
                MonitoringConsent(
                    tenant_id=tenant.id,
                    elder_id=elder.id,
                    video_monitoring_consent=True,
                    family_notifications_consent=True,
                    consented_by_name="Demo seed",
                    consented_at=datetime.utcnow(),
                    notes="Seeded for monitoring demo",
                )
            )

        now = datetime.utcnow()
        db.add_all(
            [
                CameraEvent(
                    tenant_id=tenant.id,
                    elder_id=elder.id,
                    event_type="MOTION",
                    event_timestamp=now - timedelta(hours=2),
                    severity="LOW",
                    metadata_={"zone": "living_room"},
                ),
                CameraEvent(
                    tenant_id=tenant.id,
                    elder_id=elder.id,
                    event_type="FALL",
                    event_timestamp=now - timedelta(minutes=45),
                    severity="CRITICAL",
                    clip_url="/demo/clip-fall.mp4",
                    metadata_={"confidence": 0.92},
                ),
                CameraEvent(
                    tenant_id=tenant.id,
                    elder_id=elder.id,
                    event_type="NO_MOVEMENT",
                    event_timestamp=now - timedelta(minutes=20),
                    severity="HIGH",
                    metadata_={"duration_minutes": 180},
                ),
            ]
        )
        db.add(
            Incident(
                tenant_id=tenant.id,
                elder_id=elder.id,
                incident_type="FALL_DETECTED",
                severity="HIGH",
                description="Demo incident from seed_monitoring",
                status="OPEN",
            )
        )
        db.commit()
        print("Monitoring seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_monitoring()
