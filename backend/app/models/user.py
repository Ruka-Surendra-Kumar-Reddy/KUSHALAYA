from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_tenant_status", "tenant_id", "status"),
        Index("ix_users_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=True,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(String(255))

    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    # Work phone for staff (shown on the Team page; used for call buttons and alerts).
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    role: Mapped[str] = mapped_column(
        String(50),
        default="USER",
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="ACTIVE",
        index=True,
    )

    elder_id: Mapped[int | None] = mapped_column(
        ForeignKey("elders.id"),
        nullable=True,
        index=True,
    )

    caregiver_id: Mapped[int | None] = mapped_column(
        ForeignKey("caregivers.id"),
        nullable=True,
        index=True,
    )

    portal_relationship: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
