"""One row per AI call (or cache hit) — feeds daily caps and the owner "AI usage" card.

Shared by every AI feature: write rows with app.livewell.ai_usage.record_ai_usage().
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AiUsageEvent(Base):
    __tablename__ = "ai_usage_events"
    __table_args__ = (Index("ix_ai_usage_tenant_feature_at", "tenant_id", "feature", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=True)
    feature: Mapped[str] = mapped_column(String(40), nullable=False)  # hazard_check | room_preview | …
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ok", nullable=False)  # ok | failed
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
