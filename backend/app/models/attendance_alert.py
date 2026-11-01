from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class AttendanceAlert(TimestampMixin, Base):
    """Notification log for attendance (arrival, departure, exceptions)."""

    __tablename__ = "attendance_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
    )

    attendance_id: Mapped[int | None] = mapped_column(
        ForeignKey("attendance_records.id"),
        nullable=True,
        index=True,
    )

    elder_id: Mapped[int] = mapped_column(
        ForeignKey("elders.id"),
        index=True,
    )

    caregiver_id: Mapped[int | None] = mapped_column(
        ForeignKey("caregivers.id"),
        nullable=True,
    )

    alert_type: Mapped[str] = mapped_column(String(50))
    channel: Mapped[str] = mapped_column(String(50), default="log")
    recipient_role: Mapped[str] = mapped_column(String(50))
    recipient: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="LOGGED")
    message: Mapped[str] = mapped_column(Text)
