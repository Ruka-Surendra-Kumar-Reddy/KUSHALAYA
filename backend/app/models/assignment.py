from datetime import date

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (Index("ix_assignments_tenant_status", "tenant_id", "status"),)

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

    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_date: Mapped[date | None] = mapped_column(nullable=True)
    end_date: Mapped[date | None] = mapped_column(nullable=True)

    status: Mapped[str] = mapped_column(
        String(50),
        default="ACTIVE",
        index=True,
    )
