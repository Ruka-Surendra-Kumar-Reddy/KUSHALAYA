from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class QualificationPack(TimestampMixin, Base):
    __tablename__ = "qualification_packs"

    id: Mapped[int] = mapped_column(primary_key=True)

    qualification_pack_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
    )
    qualification_name: Mapped[str] = mapped_column(String(255))
    sector_skill_council: Mapped[str] = mapped_column(String(100))
    nsqf_level: Mapped[int | None] = mapped_column(nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", index=True)
