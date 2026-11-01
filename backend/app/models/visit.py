from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class Visit(TimestampMixin, Base):
    __tablename__ = "visits"
    __table_args__ = (
        Index("ix_visits_assignment_start", "assignment_id", "scheduled_start"),
        Index("ix_visits_tenant_start", "tenant_id", "scheduled_start"),
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

    elder_id: Mapped[int] = mapped_column(
        ForeignKey("elders.id"),
        index=True,
        nullable=False,
    )

    caregiver_id: Mapped[int] = mapped_column(
        ForeignKey("caregivers.id"),
        index=True,
        nullable=False,
    )

    scheduled_start: Mapped[datetime] = mapped_column(index=True)
    scheduled_end: Mapped[datetime] = mapped_column(index=True)

    check_in_time: Mapped[datetime | None] = mapped_column(nullable=True)
    check_out_time: Mapped[datetime | None] = mapped_column(nullable=True)

    gps_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    visit_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    attendance_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("attendance_records.id"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="SCHEDULED",
        index=True,
    )
