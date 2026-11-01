from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class AttendanceRecord(TimestampMixin, Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        Index("ix_attendance_assignment", "assignment_id"),
        Index("ix_attendance_elder_checkin", "elder_id", "checkin_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=False,
    )

    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id"),
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

    checkin_time: Mapped[datetime | None] = mapped_column(nullable=True)
    checkout_time: Mapped[datetime | None] = mapped_column(nullable=True)
    visit_duration_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)

    checkin_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("caregiver_location_events.id"),
        nullable=True,
    )
    checkout_event_id: Mapped[int | None] = mapped_column(
        ForeignKey("caregiver_location_events.id"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="SCHEDULED",
        index=True,
    )
