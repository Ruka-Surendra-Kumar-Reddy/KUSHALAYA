"""A small ops notice for one staff user, closed with its × (app/livewell/visit_location.py).

One row per recipient. ``dedupe_key`` is unique across all rows, so a key names
the event and the user (``visit_loc:<job>:<event>:<user>``) and is never reused.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class StaffAlert(TimestampMixin, Base):
    __tablename__ = "staff_alerts"
    __table_args__ = (Index("ix_staff_alerts_user_open", "user_id", "dismissed_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    elder_id: Mapped[int | None] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), nullable=True, index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("care_jobs.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(40), default="visit_location")
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    path: Mapped[str] = mapped_column(String(300), default="")
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
