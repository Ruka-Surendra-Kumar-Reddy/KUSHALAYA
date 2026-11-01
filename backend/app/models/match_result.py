from sqlalchemy import Float, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MatchResult(Base):
    __tablename__ = "match_results"
    __table_args__ = (Index("ix_match_results_run_rank", "match_run_id", "rank"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    match_run_id: Mapped[int] = mapped_column(
        ForeignKey("match_runs.id"),
        index=True,
        nullable=False,
    )

    caregiver_id: Mapped[int] = mapped_column(
        ForeignKey("caregivers.id"),
        index=True,
        nullable=False,
    )

    rank: Mapped[int] = mapped_column(nullable=False)

    match_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)

    component_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(
        String(50),
        default="RECOMMENDED",
    )
