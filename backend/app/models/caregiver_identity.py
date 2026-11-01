from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class CaregiverIdentity(TimestampMixin, Base):
    __tablename__ = "caregiver_identities"

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=False,
    )

    caregiver_id: Mapped[int] = mapped_column(
        ForeignKey("caregivers.id"),
        unique=True,
        index=True,
        nullable=False,
    )

    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(50), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    mobile_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    address_line1: Mapped[str | None] = mapped_column(String(500), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    aadhaar_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    aadhaar_vid: Mapped[str | None] = mapped_column(String(50), nullable=True)

    photo_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    verification_status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        index=True,
    )

    qr_validation_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    qr_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    primary_aadhaar_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id"),
        nullable=True,
    )

    user_confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    identity_consent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
