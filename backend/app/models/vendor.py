"""A vendor the ops team works with (plumber, physio, pharmacy, ...). Sales -> Vendors.

Services are codes from ``VENDOR_SERVICES`` (the one list; the page reads it from
GET /api/v1/vendors/options). Fees are integer paise with a basis.
"""

from __future__ import annotations

from datetime import date

from datetime import datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin

VENDOR_SERVICES: tuple[tuple[str, str], ...] = (
    ("grab_bars", "Grab bar & safety installation"),
    ("plumbing", "Plumbing"),
    ("electrical", "Electrical"),
    ("carpentry", "Carpentry"),
    ("physiotherapy", "Physiotherapy"),
    ("nursing", "Nursing"),
    ("caregiver", "Caregiver / attendant"),
    ("medical_equipment", "Medical equipment"),
    ("pharmacy", "Pharmacy"),
    ("ambulance", "Ambulance"),
    ("diagnostics", "Diagnostics / lab"),
    ("cleaning", "Cleaning"),
    ("pest_control", "Pest control"),
    ("transport", "Transport"),
    ("other", "Other"),
)

FEE_BASES: tuple[tuple[str, str], ...] = (
    ("per_visit", "Per visit"),
    ("monthly", "Monthly"),
    ("one_time", "One-time"),
    ("per_job", "Per job"),
)

VENDOR_STATUSES = ("active", "inactive")


class Vendor(TimestampMixin, Base):
    __tablename__ = "vendors"
    __table_args__ = (Index("ix_vendors_tenant_status", "tenant_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone1: Mapped[str] = mapped_column(String(30), nullable=False)
    phone2: Mapped[str | None] = mapped_column(String(30), nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    #: Service codes from VENDOR_SERVICES.
    services: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    #: Free text when "other" is ticked.
    services_other: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fee_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fee_basis: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Paper agreement signed on a visit, scanned and uploaded.
    signed_agreement_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    signed_agreement_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    signed_agreement_mime: Mapped[str | None] = mapped_column(String(40), nullable=True)
    signed_agreement_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_agreement_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
