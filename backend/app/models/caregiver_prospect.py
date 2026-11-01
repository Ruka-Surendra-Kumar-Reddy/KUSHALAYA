from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class CaregiverProspect(TimestampMixin, Base):
    __tablename__ = "caregiver_prospects"
    __table_args__ = (
        Index("ix_caregiver_prospects_tenant_status", "tenant_id", "status"),
        Index("ix_caregiver_prospects_tenant_stage", "tenant_id", "stage"),
        Index("ix_caregiver_prospects_owner", "owner_user_id"),
        Index("ix_caregiver_prospects_follow_up", "next_follow_up_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=False,
    )

    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)

    stage: Mapped[str] = mapped_column(String(50), default="APPLIED", index=True)
    status: Mapped[str] = mapped_column(String(50), default="OPEN", index=True)

    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    next_follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    lost_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    years_experience: Mapped[int | None] = mapped_column(nullable=True)

    converted_caregiver_id: Mapped[int | None] = mapped_column(
        ForeignKey("caregivers.id"),
        nullable=True,
    )

    resume_parsed_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    resume_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    resume_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id"),
        nullable=True,
    )
