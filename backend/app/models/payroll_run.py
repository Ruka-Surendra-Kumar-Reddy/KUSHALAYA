from datetime import date, datetime

from sqlalchemy import Date, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class PayrollRun(TimestampMixin, Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (Index("ix_payroll_runs_tenant_period", "tenant_id", "period_start"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=False,
    )

    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", index=True)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)
    total_deductions: Mapped[float] = mapped_column(Float, default=0.0)
    total_net: Mapped[float] = mapped_column(Float, default=0.0)
    finalized_at: Mapped[datetime | None] = mapped_column(nullable=True)


class PayrollLine(Base):
    __tablename__ = "payroll_lines"
    __table_args__ = (Index("ix_payroll_lines_run", "payroll_run_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    payroll_run_id: Mapped[int] = mapped_column(
        ForeignKey("payroll_runs.id"),
        index=True,
        nullable=False,
    )

    caregiver_id: Mapped[int] = mapped_column(
        ForeignKey("caregivers.id"),
        index=True,
        nullable=False,
    )

    attendance_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("attendance_records.id"),
        nullable=True,
    )

    hours: Mapped[float] = mapped_column(Float, nullable=False)
    hourly_rate: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
