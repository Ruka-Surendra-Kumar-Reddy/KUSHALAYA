"""Persisted SafeHome 360™ on-site assessments (tenant-scoped, syncs across devices)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class HomeSafetyAssessmentRecord(TimestampMixin, Base):
    __tablename__ = "home_safety_assessments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "assessment_id", name="uq_hs_assessment_tenant_id"),
        Index("ix_hs_assessments_tenant_status", "tenant_id", "status"),
        Index("ix_hs_assessments_tenant_prospect", "tenant_id", "prospect_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=False,
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    prospect_id: Mapped[int | None] = mapped_column(
        ForeignKey("elder_prospects.id"),
        nullable=True,
        index=True,
    )
    elder_id: Mapped[int | None] = mapped_column(
        ForeignKey("elders.id"),
        nullable=True,
        index=True,
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    configuration_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Server-computed Independence Score on completion and the value the client
    # reported for the same payload (diff surfaces scoring drift in logs).
    server_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_reported_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Completed assessments are locked: every accepted change to the content
    # appends {at, by, payload_hash, independenceScore, reason} here …
    # versions / history hold earlier copies of the payload and grow to megabytes per row.
    # Deferred: loaded only when read, so lists, counts and dashboards stay fast (27 Oct).
    versions: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list, deferred=True)
    # … and the payload it replaced is kept here (newest last, capped at 10).
    history: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list, deferred=True)
