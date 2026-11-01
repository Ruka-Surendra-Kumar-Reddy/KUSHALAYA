from datetime import date, datetime

from sqlalchemy import Date, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class SubscriptionInvoice(TimestampMixin, Base):
    """Platform invoice billed to a tenant for WorkforceOS subscription."""

    __tablename__ = "subscription_invoices"
    __table_args__ = (
        Index("ix_subscription_invoices_tenant", "tenant_id", "period_start"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=False,
    )

    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("tenant_subscriptions.id"),
        index=True,
        nullable=False,
    )

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("subscription_plans.id"),
        nullable=False,
    )

    invoice_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    worker_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)

    subtotal: Mapped[float] = mapped_column(Float, default=0.0)
    tax_rate: Mapped[float] = mapped_column(Float, default=18.0)
    tax_amount: Mapped[float] = mapped_column(Float, default=0.0)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    amount_paid: Mapped[float] = mapped_column(Float, default=0.0)

    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(nullable=True)
