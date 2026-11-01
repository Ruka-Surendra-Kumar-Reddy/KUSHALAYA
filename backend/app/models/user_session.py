"""User session activity tracking (assessor / family / staff)."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("ix_user_sessions_tenant_started", "tenant_id", "started_at"),
        Index("ix_user_sessions_user_started", "user_id", "started_at"),
        Index("ix_user_sessions_actor_started", "actor_type", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=True,
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    actor_type: Mapped[str] = mapped_column(String(20), index=True)
    user_email: Mapped[str] = mapped_column(String(255))
    user_name: Mapped[str] = mapped_column(String(255), default="")
    user_role: Mapped[str] = mapped_column(String(40))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Set on sessions the server opened to continue an ended one (idle split,
    # logout-then-activity, daily system rollover). Points at the id the client
    # still sends in X-Session-ID, so a lookup by that id finds the live row.
    root_session_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )


class UserSessionEvent(Base):
    __tablename__ = "user_session_events"
    __table_args__ = (
        Index("ix_user_session_events_session_occurred", "session_id", "occurred_at"),
        Index("ix_user_session_events_tenant_occurred", "tenant_id", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user_sessions.id"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=True,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_kind: Mapped[str] = mapped_column(String(20), default="api_call")
    action: Mapped[str] = mapped_column(String(120))
    method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
