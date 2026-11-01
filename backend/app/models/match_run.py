from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MatchRun(Base):
    __tablename__ = "match_runs"
    __table_args__ = (Index("ix_match_runs_tenant_created", "tenant_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=False,
    )

    elder_id: Mapped[int] = mapped_column(
        ForeignKey("elders.id"),
        index=True,
        nullable=False,
    )

    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    algorithm_version: Mapped[str] = mapped_column(
        String(20),
        default="rules-v1",
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="COMPLETED",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
