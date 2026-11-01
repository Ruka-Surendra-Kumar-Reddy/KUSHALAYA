"""A client's care plan (one row per plan period): KushAlaya Assurance / Total Care /
Privilege / Signature, billed yearly or monthly. Plans come from
app/livewell/care_plan_catalog.py; the amount is copied from the catalog when the
row is created so later price changes never rewrite history.

Lifecycle: pending_approval -> active (Authorize) -> expired (end date passed,
computed) or cancelled. Money is integer paise.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin

PLAN_STATUSES = ("pending_approval", "active", "cancelled")
PAYMENT_STATUSES = ("unpaid", "paid")


class CustomerPlan(TimestampMixin, Base):
    __tablename__ = "customer_plans"
    __table_args__ = (
        Index("ix_customer_plans_tenant_status", "tenant_id", "status"),
        Index("ix_customer_plans_elder", "elder_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), nullable=False)
    #: The enquiry this plan was won from (plain id: the lead may be deleted later).
    prospect_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    plan_id: Mapped[str] = mapped_column(String(40), nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String(10), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Coupon given (e.g. PAYNOW3) and what it took off the catalog price; amount_paise is after it.
    coupon_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    discount_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    payment_status: Mapped[str] = mapped_column(String(10), nullable=False, default="unpaid")
    payment_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_approval")
    authorized_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
