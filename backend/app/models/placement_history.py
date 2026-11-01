from datetime import date, datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PlacementHistory(Base):
    __tablename__ = "placement_history"
    __table_args__ = (
        Index("ix_placement_history_caregiver", "caregiver_id"),
        Index("ix_placement_history_elder", "elder_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
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

    assignment_id: Mapped[int | None] = mapped_column(
        ForeignKey("assignments.id"),
        nullable=True,
    )

    start_date: Mapped[date | None] = mapped_column(nullable=True)
    end_date: Mapped[date | None] = mapped_column(nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
    )
