from datetime import date

from sqlalchemy import Float, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class CaregiverPayRate(TimestampMixin, Base):
    __tablename__ = "caregiver_pay_rates"
    __table_args__ = (
        Index("ix_pay_rates_caregiver_effective", "caregiver_id", "effective_from"),
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

    hourly_rate: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(default="INR")
    effective_from: Mapped[date] = mapped_column(nullable=False)
