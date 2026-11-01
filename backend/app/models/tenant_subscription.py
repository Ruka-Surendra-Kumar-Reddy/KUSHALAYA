from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class TenantSubscription(TimestampMixin, Base):
    """Active subscription for a tenant (one per tenant)."""

    __tablename__ = "tenant_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        unique=True,
        index=True,
        nullable=False,
    )

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("subscription_plans.id"),
        index=True,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(String(30), default="TRIAL", index=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    current_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
