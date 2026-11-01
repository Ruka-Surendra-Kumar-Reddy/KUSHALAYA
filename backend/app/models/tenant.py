from sqlalchemy import Float, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (Index("ix_tenants_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
    )

    register_slug: Mapped[str | None] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
        index=True,
    )

    email: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str] = mapped_column(String(50))
    address: Mapped[str] = mapped_column(String(500))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100))

    country: Mapped[str] = mapped_column(
        String(100),
        default="India",
    )

    market: Mapped[str] = mapped_column(
        String(10),
        default="IN",
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="ACTIVE",
        index=True,
    )

    vertical: Mapped[str] = mapped_column(
        String(50),
        default="LIVEWELL360",
        index=True,
    )

    theme: Mapped[str] = mapped_column(
        String(50),
        default="classic",
    )

    logo_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    portal_title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    bench_cost_per_caregiver_month_inr: Mapped[float] = mapped_column(
        Float,
        default=15_000.0,
        nullable=False,
    )

    elder_field_schema: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )

    caregiver_field_schema: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )

    monitoring_config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )

    workflow_config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )

    payroll_config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )
