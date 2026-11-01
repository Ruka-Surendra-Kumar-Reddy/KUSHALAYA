"""GST tax invoices, bills of supply and credit notes (FIX_TODO #102).

One document per payment: an invoice when a family pays an order / quote /
service request from the wallet, and a credit note (referencing that invoice)
when the payment is refunded. Numbers come from `invoice_counters`, one row per
(tenant, financial year, series), incremented inside the same transaction that
inserts the document — so a rolled-back payment never burns a number (no gaps).

All amounts are integer paise.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin

DOC_KINDS = ("invoice", "credit_note")
# tax_invoice: GSTIN set, GST shown. bill_of_supply: no GSTIN yet, receipt without GST breakdown.
DOC_TYPES = ("tax_invoice", "bill_of_supply")


class InvoiceCounter(Base):
    """Running number per tenant / financial year (fy = start year, Apr–Mar) / series."""

    __tablename__ = "invoice_counters"
    __table_args__ = (UniqueConstraint("tenant_id", "fy", "series", name="uq_invoice_counters_tenant_fy_series"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    fy: Mapped[int] = mapped_column(Integer, nullable=False)
    series: Mapped[str] = mapped_column(String(20), nullable=False)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TaxInvoice(TimestampMixin, Base):
    __tablename__ = "tax_invoices"
    __table_args__ = (
        UniqueConstraint("tenant_id", "kind", "number", name="uq_tax_invoices_tenant_kind_number"),
        # One invoice and at most one credit note per paid thing.
        UniqueConstraint("tenant_id", "kind", "source_type", "source_id", name="uq_tax_invoices_source"),
        Index("ix_tax_invoices_tenant_issued", "tenant_id", "issued_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), index=True, nullable=False)

    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="invoice")
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False, default="bill_of_supply")
    number: Mapped[str] = mapped_column(String(20), nullable=False)
    fy: Mapped[int] = mapped_column(Integer, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # What was paid for: ("order", "12") or ("service_request", "fsr_ab12...").
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    wallet_transaction_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    original_invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("tax_invoices.id", ondelete="SET NULL"), nullable=True
    )

    # Snapshots at issue time — later edits to business details don't rewrite old invoices.
    supplier: Mapped[dict] = mapped_column(JSON, default=dict)
    customer: Mapped[dict] = mapped_column(JSON, default=dict)
    place_of_supply: Mapped[str] = mapped_column(String(4), default="")
    intra_state: Mapped[bool] = mapped_column(default=True)
    # [{description, hsn_sac, qty, unit_paise, amount_paise}]
    lines: Mapped[list] = mapped_column(JSON, default=list)

    gross_paise: Mapped[int] = mapped_column(Integer, default=0)
    discount_paise: Mapped[int] = mapped_column(Integer, default=0)
    taxable_paise: Mapped[int] = mapped_column(Integer, default=0)
    cgst_paise: Mapped[int] = mapped_column(Integer, default=0)
    sgst_paise: Mapped[int] = mapped_column(Integer, default=0)
    igst_paise: Mapped[int] = mapped_column(Integer, default=0)
    total_paise: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(String(300), default="")
