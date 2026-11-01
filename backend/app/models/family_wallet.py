"""Family prepaid wallet — one per elder, with an append-only transaction ledger.

Money is stored as integer minor units (paise), never float: float arithmetic
silently loses precision and money must reconcile exactly.

`wallet_transactions` is the source of truth; `family_wallets.balance_minor` is
a cached projection of SUM(amount_minor) over successful rows, kept in step
inside the same transaction that writes the ledger entry.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin

WALLET_STATUSES = ("active", "frozen")

# Credits are positive, debits negative — so SUM(amount_minor) == balance.
TRANSACTION_KINDS = ("recharge", "debit", "refund", "adjustment")
CREDIT_KINDS = frozenset({"recharge", "refund"})
DEBIT_KINDS = frozenset({"debit"})

TRANSACTION_STATUSES = ("pending", "success", "failed")


class FamilyWallet(TimestampMixin, Base):
    """Prepaid balance held against one elder, topped up by any linked family member."""

    __tablename__ = "family_wallets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "elder_id", name="uq_family_wallets_tenant_elder"),
        CheckConstraint("balance_minor >= 0", name="ck_family_wallets_balance_non_negative"),
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

    balance_minor: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)

    # Bumped on every balance write; lets a concurrent update detect a lost race
    # on SQLite, where SELECT ... FOR UPDATE is a no-op.
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WalletTransaction(TimestampMixin, Base):
    """Append-only ledger entry. Never updated except pending → success/failed."""

    __tablename__ = "wallet_transactions"
    __table_args__ = (
        # Hard guarantee against double-credit from retried webhooks / double taps.
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_wallet_transactions_tenant_idempotency",
        ),
        Index("ix_wallet_transactions_wallet_created", "wallet_id", "created_at"),
        Index("ix_wallet_transactions_gateway_payment", "gateway_payment_id"),
        Index("ix_wallet_transactions_reference", "reference_type", "reference_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=False,
    )
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("family_wallets.id"),
        index=True,
        nullable=False,
    )

    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    # Signed: credits positive, debits negative.
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    status: Mapped[str] = mapped_column(String(16), default="success", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)

    # What this entry paid for — e.g. ("service_request", "fsr_ab12cd34ef56").
    reference_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    gateway: Mapped[str | None] = mapped_column(String(30), nullable=True)
    gateway_order_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    gateway_payment_id: Mapped[str | None] = mapped_column(String(80), nullable=True)

    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
