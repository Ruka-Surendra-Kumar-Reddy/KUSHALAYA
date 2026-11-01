from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RecommendationFeedback(Base):
    __tablename__ = "recommendation_feedback"
    __table_args__ = (Index("ix_recommendation_feedback_result", "match_result_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)

    match_result_id: Mapped[int] = mapped_column(
        ForeignKey("match_results.id"),
        index=True,
        nullable=False,
    )

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    rating: Mapped[int] = mapped_column(nullable=False)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
    )
