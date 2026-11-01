from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PayrollDeduction(Base):
    """Statutory payroll deductions per caregiver per run (PF, ESI, PT, TDS)."""

    __tablename__ = "payroll_deductions"
    __table_args__ = (
        Index("ix_payroll_deductions_run", "payroll_run_id"),
        Index("ix_payroll_deductions_caregiver", "caregiver_id"),
    )

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

    deduction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    base_amount: Mapped[float] = mapped_column(Float, default=0.0)
    rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
