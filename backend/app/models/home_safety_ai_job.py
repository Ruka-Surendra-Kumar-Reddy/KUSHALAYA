"""AI visualization jobs — room photo → tier concept image (RunPod deferred in Phase 1)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class HomeSafetyAIJob(TimestampMixin, Base):
    __tablename__ = "home_safety_ai_jobs"
    __table_args__ = (
        Index("ix_hs_ai_jobs_tenant_assessment", "tenant_id", "assessment_id"),
        Index("ix_hs_ai_jobs_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=False,
    )

    assessment_id: Mapped[str] = mapped_column(String(64), index=True)
    prospect_id: Mapped[int | None] = mapped_column(
        ForeignKey("elder_prospects.id"),
        nullable=True,
    )
    elder_id: Mapped[int | None] = mapped_column(
        ForeignKey("elders.id"),
        nullable=True,
    )

    room_type: Mapped[str] = mapped_column(String(32))
    package_level: Mapped[str] = mapped_column(String(32))
    source_document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(String(50), default="queued", index=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    original_image_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    generated_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id"),
        nullable=True,
    )
    generated_image_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    negative_prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    workflow_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    approved_solution_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    generation_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    event_log: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Session that started this job (for activity tracking of AI returns).
    origin_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    # AI room preview (2026-10-11): background render progress + room-unchanged check.
    progress_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    render_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # public_id of the job this one re-ran (counts toward max_regenerations_per_tier).
    regenerated_from: Mapped[str | None] = mapped_column(String(32), nullable=True)
