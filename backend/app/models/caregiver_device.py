from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class CaregiverDevice(TimestampMixin, Base):
    __tablename__ = "caregiver_devices"
    __table_args__ = (
        Index("ix_caregiver_devices_device", "device_id", unique=True),
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

    device_id: Mapped[str] = mapped_column(String(255), nullable=False)
    device_label: Mapped[str | None] = mapped_column(String(200), nullable=True)

    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
