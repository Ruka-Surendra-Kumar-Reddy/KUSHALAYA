from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class SubscriptionPlan(TimestampMixin, Base):
    """Platform SaaS plan catalog (WorkforceOS → agency tenants)."""

    __tablename__ = "subscription_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    market: Mapped[str] = mapped_column(String(10), default="IN", index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    billing_model: Mapped[str] = mapped_column(
        String(20),
        default="PER_WORKER",
    )
    base_price_inr: Mapped[float] = mapped_column(Float, default=0.0)
    price_per_worker_inr: Mapped[float] = mapped_column(Float, default=0.0)
    included_workers: Mapped[int] = mapped_column(Integer, default=0)
    max_workers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trial_days: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
