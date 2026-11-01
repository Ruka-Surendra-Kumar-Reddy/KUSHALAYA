from sqlalchemy import ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class WorkflowEvent(TimestampMixin, Base):
    """Immutable domain event log for workflow automation."""

    __tablename__ = "workflow_events"
    __table_args__ = (
        Index("ix_workflow_events_tenant_created", "tenant_id", "created_at"),
        Index("ix_workflow_events_type", "event_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
    )

    event_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(nullable=True)

    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    processing_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
