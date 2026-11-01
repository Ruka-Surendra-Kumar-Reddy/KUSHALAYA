from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CaregiverLocationEvent(Base):
    __tablename__ = "caregiver_location_events"
    __table_args__ = (
        Index("ix_location_events_caregiver_ts", "caregiver_id", "event_timestamp"),
        Index("ix_location_events_elder_ts", "elder_id", "event_timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=False,
    )

    caregiver_id: Mapped[int] = mapped_column(
        ForeignKey("caregivers.id"),
        index=True,
        nullable=False,
    )

    elder_id: Mapped[int] = mapped_column(
        ForeignKey("elders.id"),
        index=True,
        nullable=False,
    )

    assignment_id: Mapped[int | None] = mapped_column(
        ForeignKey("assignments.id"),
        index=True,
        nullable=True,
    )

    event_type: Mapped[str] = mapped_column(String(50), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_meters: Mapped[float | None] = mapped_column(Float, nullable=True)

    device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    event_timestamp: Mapped[datetime] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
