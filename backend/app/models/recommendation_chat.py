"""Assessor recommendation chat — conversation threads grounded in an assessment."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RecommendationConversation(Base):
    __tablename__ = "recommendation_conversations"
    __table_args__ = (
        Index("ix_rec_chat_tenant_assessment", "tenant_id", "assessment_id"),
        Index("ix_rec_chat_tenant_user", "tenant_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assessment_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    elder_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prospect_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | archived
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    origin_session_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class RecommendationMessage(Base):
    __tablename__ = "recommendation_messages"
    __table_args__ = (
        Index("ix_rec_msg_conversation_created", "conversation_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("recommendation_conversations.id"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    structured: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_deployment: Mapped[str | None] = mapped_column(String(120), nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    validation_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    requires_human_review: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
