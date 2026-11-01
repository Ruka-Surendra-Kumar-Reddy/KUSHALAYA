from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class TrainingProgram(TimestampMixin, Base):
    __tablename__ = "training_programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    qualification_pack_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE")


class CaregiverProgramEnrollment(TimestampMixin, Base):
    __tablename__ = "caregiver_program_enrollments"
    __table_args__ = (
        Index("ix_enrollment_caregiver_program", "caregiver_id", "program_id", unique=True),
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

    program_id: Mapped[int] = mapped_column(
        ForeignKey("training_programs.id"),
        index=True,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="ENROLLED",
        index=True,
    )
    assessment_score: Mapped[float | None] = mapped_column(nullable=True)
