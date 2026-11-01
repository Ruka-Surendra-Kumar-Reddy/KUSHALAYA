"""KushLife weekly summary: drafted by the jobs runner each Monday, approved by the care manager.

One row per client per week (``week_start`` = Monday, IST, of the week summarised). The unique
constraint is the dedupe: the timer runs every 2 minutes, so a second draft for the same
client and week is never created. Only ``approved`` rows are ever shown to the family.
"""

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class KushLifeWeekly(TimestampMixin, Base):
    __tablename__ = "kushlife_weekly_summaries"
    __table_args__ = (UniqueConstraint("elder_id", "week_start", name="uq_kushlife_weekly_elder_week"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), index=True)
    week_start: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  # draft | approved | skipped (no KushLife data; never shown)
    draft_text: Mapped[str] = mapped_column(Text, default="")
    text: Mapped[str] = mapped_column(Text, default="")
    stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    edited_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
