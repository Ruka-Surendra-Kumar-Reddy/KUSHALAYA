from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class ShiftSwapRequest(TimestampMixin, Base):
    """Caregiver requests another worker to cover a scheduled visit."""

    __tablename__ = "shift_swap_requests"
    __table_args__ = (
        Index("ix_shift_swap_tenant_status", "tenant_id", "status"),
        Index("ix_shift_swap_visit", "visit_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=False,
    )

    visit_id: Mapped[int] = mapped_column(
        ForeignKey("visits.id"),
        index=True,
        nullable=False,
    )

    requesting_caregiver_id: Mapped[int] = mapped_column(
        ForeignKey("caregivers.id"),
        index=True,
        nullable=False,
    )

    replacement_caregiver_id: Mapped[int | None] = mapped_column(
        ForeignKey("caregivers.id"),
        nullable=True,
        index=True,
    )

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        default="PENDING",
        index=True,
    )

    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
