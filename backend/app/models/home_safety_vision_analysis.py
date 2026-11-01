"""Cached Contract C room-analysis results — keyed by photo SHA-256 + model."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class HomeSafetyVisionAnalysis(TimestampMixin, Base):
    __tablename__ = "home_safety_vision_analyses"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "document_id",
            "sha256",
            "model_version",
            name="uq_hs_vision_tenant_doc_sha_model",
        ),
        Index("ix_hs_vision_tenant_document", "tenant_id", "document_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"),
        index=True,
        nullable=False,
    )
    assessment_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    room_type: Mapped[str | None] = mapped_column(String(32), nullable=True)

    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)

    status: Mapped[str] = mapped_column(String(32), default="SUCCEEDED")
    response_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    mapped_suggestions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
