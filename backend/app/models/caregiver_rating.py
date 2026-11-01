from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CaregiverRating(Base):
    __tablename__ = "caregiver_ratings"
    __table_args__ = (Index("ix_caregiver_ratings_caregiver", "caregiver_id"),)

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

    rating: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(50))

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
    )
