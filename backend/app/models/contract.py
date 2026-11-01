"""Contracts signed inside the app: vendor agreements and client service contracts.

- ``ContractTemplate``: versioned wording. Editing makes a new row (same ``group_key``,
  ``version`` + 1); old versions stay so a signed contract can always point at the
  exact template it came from.
- ``ContractSignatory``: an admin's saved signature (name, designation, image), reused
  by "Sign & send".
- ``Contract``: one document for one vendor or client. The text is rendered from the
  template when it is created and frozen once KushAlaya signs it. Both signatures,
  their audit details and the SHA-256 of the exact text are stored here; the signed
  PDF goes to document storage (``document_id``).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin

CONTRACT_KINDS: tuple[tuple[str, str], ...] = (
    ("vendor", "Vendor agreement"),
    ("client", "Client service contract"),
)

#: draft -> awaiting_company -> sent -> viewed -> signed; or cancelled. "expired" is
#: worked out from ``expires_at`` (see contracts.effective_status).
CONTRACT_STATUSES = ("draft", "awaiting_company", "sent", "viewed", "signed", "cancelled")


class ContractTemplate(TimestampMixin, Base):
    __tablename__ = "contract_templates"
    __table_args__ = (Index("ix_contract_templates_tenant_kind", "tenant_id", "kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    #: Same for every version of one template.
    group_key: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ContractSignatory(TimestampMixin, Base):
    __tablename__ = "contract_signatories"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    designation: Mapped[str] = mapped_column(String(120), nullable=False)
    #: "drawn" (PNG data URL in signature_png) or "typed" (signature_text).
    signature_kind: Mapped[str] = mapped_column(String(10), nullable=False, default="drawn")
    signature_png: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_text: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Contract(TimestampMixin, Base):
    __tablename__ = "contracts"
    __table_args__ = (
        Index("ix_contracts_tenant_status", "tenant_id", "status"),
        Index("ix_contracts_elder", "elder_id"),
        Index("ix_contracts_vendor", "vendor_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("contract_templates.id", ondelete="SET NULL"), nullable=True)
    template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elder_id: Mapped[int | None] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), nullable=True)
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id", ondelete="CASCADE"), nullable=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    fields: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    signer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    signer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signer_mobile: Mapped[str | None] = mapped_column(String(30), nullable=True)
    signer_relation: Mapped[str | None] = mapped_column(String(60), nullable=True)

    #: Random per contract; rotated by "Resend" so an old link stops working.
    token_nonce: Mapped[str | None] = mapped_column(String(40), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # KushAlaya's signature (always first).
    company_signer_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    company_signer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company_signer_designation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    company_signer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_signature_kind: Mapped[str | None] = mapped_column(String(10), nullable=True)
    company_signature_png: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_signature_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    company_signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    company_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    company_user_agent: Mapped[str | None] = mapped_column(String(400), nullable=True)
    company_text_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # The vendor's / client's signature.
    signed_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    signature_kind: Mapped[str | None] = mapped_column(String(10), nullable=True)
    signature_png: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    signer_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signer_user_agent: Mapped[str | None] = mapped_column(String(400), nullable=True)
    signed_text_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)

    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    #: Small free-form history: [{"at", "event", "by"}].
    history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
