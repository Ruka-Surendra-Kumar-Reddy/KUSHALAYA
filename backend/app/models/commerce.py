"""Products, coupons and orders. Money is integer paise (see app/core/money.py).

Selling price = cost × (1 + margin). GST is added on top when an order is priced.
Discounts never take an order below its cost.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin

ORDER_STATUSES = (
    "pending_approval", "approved", "quoted", "family_accepted", "scheduled", "completed", "cancelled",
)


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (Index("ix_products_tenant_name", "tenant_id", "name", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    # Catalog code from default_catalog.json (e.g. "BTH-002"); empty for products added by hand.
    product_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    category: Mapped[str] = mapped_column(String(60), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    cost_paise: Mapped[int] = mapped_column(default=0)
    # Margin in basis points (2500 = 25%), so the price stays integer maths.
    margin_bp: Mapped[int] = mapped_column(default=3000)
    active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    # Assessment question ids this product fixes (drives suggestions).
    fixes: Mapped[list] = mapped_column(JSON, default=list)
    # Uploaded photo (storage key). Empty: the marketing-site picture for this product, if any.
    image_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_version: Mapped[int] = mapped_column(default=0)


class Coupon(TimestampMixin, Base):
    __tablename__ = "coupons"
    __table_args__ = (Index("ix_coupons_tenant_code", "tenant_id", "code", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(10), default="percent")  # percent | amount
    # percent: basis points (1000 = 10%); amount: paise.
    value: Mapped[int] = mapped_column(default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_uses: Mapped[int | None] = mapped_column(nullable=True)
    used_count: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(default=True)
    note: Mapped[str] = mapped_column(String(200), default="")


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="approved", index=True)
    # [{product_id, name, qty, unit_paise, cost_paise}]
    lines: Mapped[list] = mapped_column(JSON, default=list)
    subtotal_paise: Mapped[int] = mapped_column(default=0)
    cost_paise: Mapped[int] = mapped_column(default=0)
    discount_paise: Mapped[int] = mapped_column(default=0)
    discount_reason: Mapped[str] = mapped_column(String(200), default="")
    coupon_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    gst_bp: Mapped[int] = mapped_column(default=1800)
    gst_paise: Mapped[int] = mapped_column(default=0)
    total_paise: Mapped[int] = mapped_column(default=0)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    job_id: Mapped[int | None] = mapped_column(nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Quote sent to the family (status quoted) and their answer. Paid from the family wallet.
    quoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    family_note: Mapped[str] = mapped_column(String(300), default="")
    paid_paise: Mapped[int] = mapped_column(default=0)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    wallet_transaction_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
