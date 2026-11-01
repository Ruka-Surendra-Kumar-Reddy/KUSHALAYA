from sqlalchemy import ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class Caregiver(TimestampMixin, Base):
    __tablename__ = "caregivers"
    __table_args__ = (
        Index("ix_caregivers_tenant_status", "tenant_id", "status"),
        Index("ix_caregivers_tenant_created", "tenant_id", "created_at"),
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
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    aadhaar_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    years_experience: Mapped[int | None] = mapped_column(nullable=True)

    background_check_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    police_verification_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    custom_attributes: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="ACTIVE",
        index=True,
    )

    # Manager (a CARE_MANAGER user) this record reports to; managers see only their team.
    manager_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
