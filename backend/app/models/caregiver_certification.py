from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class CaregiverCertification(TimestampMixin, Base):
    __tablename__ = "caregiver_certifications"
    __table_args__ = (
        Index("ix_caregiver_certs_caregiver", "caregiver_id"),
        Index("ix_caregiver_certs_status", "verification_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=False,
    )

    caregiver_id: Mapped[int] = mapped_column(
        ForeignKey("caregivers.id"),
        index=True,
        nullable=False,
    )

    certification_name: Mapped[str] = mapped_column(String(255))
    qualification_pack_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    issuing_body: Mapped[str] = mapped_column(String(255))
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    certificate_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    certificate_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id"),
        nullable=True,
    )

    verification_status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        index=True,
    )
