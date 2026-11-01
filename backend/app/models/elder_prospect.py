from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class ElderProspect(TimestampMixin, Base):
    __tablename__ = "elder_prospects"
    __table_args__ = (
        Index("ix_elder_prospects_tenant_status", "tenant_id", "status"),
        Index("ix_elder_prospects_tenant_stage", "tenant_id", "stage"),
        Index("ix_elder_prospects_owner", "owner_user_id"),
        Index("ix_elder_prospects_follow_up", "next_follow_up_at"),
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
    #: Caller IP for public website enquiries — used only to rate limit them.
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    stage: Mapped[str] = mapped_column(String(50), default="NEW", index=True)
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
    care_level: Mapped[str | None] = mapped_column(String(100), nullable=True)

    converted_elder_id: Mapped[int | None] = mapped_column(
        ForeignKey("elders.id"),
        nullable=True,
    )

    # --- Lead tracking (FIX 107/108; website enquiries only) ---
    utm_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(100), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(150), nullable=True)
    referrer_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    landing_page: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: A family's referral code (/r/<code>); resolves to the referring client.
    referral_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    #: True / False when a pincode was checked against Settings → Website service areas.
    area_served: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    #: Requested KushCare Discovery slot, e.g. "2026-10-12 morning".
    assessment_slot: Mapped[str | None] = mapped_column(String(40), nullable=True)
    assessment_fee_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assessment_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assessment_paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
