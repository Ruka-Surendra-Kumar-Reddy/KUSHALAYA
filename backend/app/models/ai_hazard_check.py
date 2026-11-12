"""AI room hazard check: one row per photo check, plus per-hazard staff feedback.

Nothing here is applied to an assessment by itself. `hazards` holds what the model
reported (codes from our own list only); each entry carries its own staff decision.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class AiHazardCheck(TimestampMixin, Base):
    __tablename__ = "ai_hazard_checks"
    __table_args__ = (
        Index("ix_ai_hazard_checks_tenant_sha", "tenant_id", "sha256"),
        Index("ix_ai_hazard_checks_tenant_elder", "tenant_id", "elder_id"),
        Index("ix_ai_hazard_checks_tenant_assessment", "tenant_id", "assessment_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True, nullable=False)
    elder_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prospect_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assessment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    room_type: Mapped[str | None] = mapped_column(String(32), nullable=True)

    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    catalog_hash: Mapped[str | None] = mapped_column(String(16), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # queued | running | succeeded | failed
    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    stage: Mapped[str | None] = mapped_column(String(80), nullable=True)
    hazards: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Room checks are for our team; a care manager shares one with the family on purpose.
    shared_with_family_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    shared_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AiHazardFeedback(TimestampMixin, Base):
    """Accept / reject per hazard code, kept for tuning thresholds and prompts later."""

    __tablename__ = "ai_hazard_feedback"
    __table_args__ = (Index("ix_ai_hazard_feedback_tenant_code", "tenant_id", "hazard_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    check_id: Mapped[int] = mapped_column(ForeignKey("ai_hazard_checks.id"), index=True, nullable=False)
    hazard_code: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)  # accepted | rejected
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
