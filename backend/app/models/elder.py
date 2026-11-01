from datetime import date

from sqlalchemy import ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class Elder(TimestampMixin, Base):
    __tablename__ = "elders"
    __table_args__ = (
        Index("ix_elders_tenant_status", "tenant_id", "status"),
        Index("ix_elders_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=False,
    )

    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))

    date_of_birth: Mapped[date | None] = mapped_column(nullable=True)
    gender: Mapped[str | None] = mapped_column(String(50), nullable=True)

    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    emergency_contact_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    emergency_contact_phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    medical_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    mobility_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    care_level: Mapped[str | None] = mapped_column(String(100), nullable=True)

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
