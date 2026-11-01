from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CaregiverSkill(Base):
    __tablename__ = "caregiver_skills"

    id: Mapped[int] = mapped_column(primary_key=True)

    caregiver_id: Mapped[int] = mapped_column(
        ForeignKey("caregivers.id"),
        index=True,
        nullable=False,
    )

    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id"),
        index=True,
        nullable=False,
    )

    experience_years: Mapped[int | None] = mapped_column(nullable=True)
    certified: Mapped[bool] = mapped_column(Boolean, default=False)
    certification_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
