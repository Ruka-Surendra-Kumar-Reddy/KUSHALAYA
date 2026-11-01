"""DPDP Act (#104): consent records and data-rights requests.

``privacy_consents`` is append-only: every grant or change is a new row, so the history
shows who consented, when, to which notice version and for which purposes. The newest row
per (user, subject, elder) is the one in force.

``privacy_data_requests`` holds "Delete my account" requests waiting for an admin.
Exports are self-service and recorded in ``audit_logs`` only.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class PrivacyConsent(Base):
    __tablename__ = "privacy_consents"
    __table_args__ = (Index("ix_privacy_consents_user_subject", "user_id", "subject", "elder_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    # The account that gave (or recorded) the consent.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    # "family" = the account holder's own data; "elder" = the client's data.
    subject: Mapped[str] = mapped_column(String(16), nullable=False, default="family")
    elder_id: Mapped[int | None] = mapped_column(ForeignKey("elders.id", ondelete="SET NULL"), nullable=True)
    notice_version: Mapped[str] = mapped_column(String(32), nullable=False)
    purposes: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Who actually agreed, in their words ("Self", "Ravi (son) on behalf of Mrs K").
    consented_by_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    relationship: Mapped[str | None] = mapped_column(String(64), nullable=True)
    method: Mapped[str] = mapped_column(String(32), nullable=False, default="family_portal")
    withdrawn: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class PrivacyDataRequest(TimestampMixin, Base):
    __tablename__ = "privacy_data_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    elder_id: Mapped[int | None] = mapped_column(ForeignKey("elders.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="DELETE")
    # "account" = my login and my details; "household" = also the client's records.
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="account")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING", index=True)
    requester_label: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
