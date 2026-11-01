"""KushLife K3 + Phase 5 (#100 #106): monthly letter, visit voice notes, visit ratings, NPS.

* ``KushLifeMonthly``: one letter per client per month (``month_start`` = 1st of the month
  summarised). The unique constraint is the dedupe for the 2-minute jobs timer. Only
  ``approved`` rows reach the family.
* ``VisitVoiceNote``: a short recording on a visit. Staff can always hear it; the family
  only once a manager ticks ``share_with_family``.
* ``VisitRating``: 1–5 after a visit, once per visit per family login.
* ``NpsResponse``: "How likely are you to recommend Kushalaya?" 0–10, asked every 90 days.
  ``score`` is null when the family member dismissed the question (asked again later).

Low ratings (≤ 2) and detractors (0–6) stay in "Needs attention" until ``reviewed_at``.
"""

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class KushLifeMonthly(TimestampMixin, Base):
    __tablename__ = "kushlife_monthly_letters"
    __table_args__ = (UniqueConstraint("elder_id", "month_start", name="uq_kushlife_monthly_elder_month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), index=True)
    month_start: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  # draft | approved | skipped
    draft_text: Mapped[str] = mapped_column(Text, default="")
    text: Mapped[str] = mapped_column(Text, default="")
    manager_note: Mapped[str] = mapped_column(Text, default="")
    next_plan: Mapped[str] = mapped_column(Text, default="")
    stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    edited_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VisitVoiceNote(TimestampMixin, Base):
    __tablename__ = "visit_voice_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), index=True)
    care_job_id: Mapped[int] = mapped_column(ForeignKey("care_jobs.id", ondelete="CASCADE"), index=True)
    storage_key: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(80), default="audio/webm")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    recorded_by_name: Mapped[str] = mapped_column(String(200), default="")
    share_with_family: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    shared_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    shared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VisitRating(TimestampMixin, Base):
    __tablename__ = "visit_ratings"
    __table_args__ = (UniqueConstraint("care_job_id", "user_id", name="uq_visit_ratings_job_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), index=True)
    care_job_id: Mapped[int] = mapped_column(ForeignKey("care_jobs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NpsResponse(TimestampMixin, Base):
    __tablename__ = "nps_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # null = dismissed
    reason: Mapped[str] = mapped_column(Text, default="")
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
