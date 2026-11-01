"""A care plan bought on the website with "Buy now" (Razorpay).

One row per checkout attempt: created when the Razorpay order is made, marked
"paid" exactly once (checkout callback or webhook, whichever comes first), at
which point the lead is won and a CustomerPlan is added for admin approval.
A pay-as-you-go visit (plan_id "single-visit", billing_cycle "once") adds no plan:
it becomes a paid family service request (ops Visits -> Requests) instead.
The price is fixed here at order time, so a coupon that expires mid-checkout
never changes what the customer paid. Money is integer paise.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class PlanPurchase(TimestampMixin, Base):
    __tablename__ = "plan_purchases"
    __table_args__ = (
        Index("ix_plan_purchases_order", "gateway_order_id", unique=True),
        Index("ix_plan_purchases_ip_created", "source_ip", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    #: The website lead (ElderProspect) — plain id, the lead may be deleted later.
    prospect_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    plan_id: Mapped[str] = mapped_column(String(40), nullable=False)
    billing_cycle: Mapped[str] = mapped_column(String(10), nullable=False)
    list_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    coupon_code: Mapped[str | None] = mapped_column(String(40), nullable=True)

    gateway: Mapped[str] = mapped_column(String(20), nullable=False, default="razorpay")
    gateway_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gateway_payment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: created -> paid
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="created")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    customer_plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Single visit only: {"need", "note", "preferred_date", "time_of_day"} from the form.
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    #: Single visit only: the paid service request made on the client (fsr_…).
    service_request_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
