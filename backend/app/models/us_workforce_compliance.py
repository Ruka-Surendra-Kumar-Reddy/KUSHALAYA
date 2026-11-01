from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class USWorkforceCompliance(TimestampMixin, Base):
    """US FCRA background check, classification, and bonding — per caregiver."""

    __table_args__ = (
        Index("ix_us_compliance_tenant", "tenant_id"),
    )

    __tablename__ = "us_workforce_compliance"

    caregiver_id: Mapped[int] = mapped_column(
        ForeignKey("caregivers.id"),
        primary_key=True,
    )

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=False,
    )

    classification: Mapped[str] = mapped_column(
        String(30),
        default="W2_EMPLOYEE",
        nullable=False,
    )

    ssn_last_four: Mapped[str | None] = mapped_column(String(4), nullable=True)
    background_check_status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
    )
    background_check_provider_ref: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    is_insured_bonded: Mapped[bool] = mapped_column(Boolean, default=False)
    liability_insurance_policy_num: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
