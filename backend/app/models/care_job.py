"""Scheduled work for a client: a care visit, an assessment or a product install.

One row per job. The manager schedules it (date, time, place, tasks, caregiver);
the caregiver moves it through on_the_way → checked_in → completed in the field app.
"""

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin

JOB_KINDS = ("visit", "assessment", "install")
JOB_STATUSES = ("requested", "scheduled", "on_the_way", "checked_in", "completed", "cancelled", "missed")


class CareJob(TimestampMixin, Base):
    __tablename__ = "care_jobs"
    __table_args__ = (
        Index("ix_care_jobs_tenant_when", "tenant_id", "scheduled_at"),
        # One job per series per IST day — repeat generation is idempotent.
        Index("uq_care_jobs_series_date", "series_id", "series_date", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="visit")
    title: Mapped[str] = mapped_column(String(200), default="")
    tasks: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(500), default="")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(nullable=True)
    caregiver_id: Mapped[int | None] = mapped_column(
        ForeignKey("caregivers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Home assessments are done by the client's care manager (a staff user), not a caregiver.
    assignee_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="scheduled", index=True)
    # Links: the family request it came from, the assessment it produced.
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assessment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    product_ids: Mapped[str] = mapped_column(String(500), default="")
    staff_note: Mapped[str] = mapped_column(Text, default="")
    caregiver_note: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Visit report: {"checks": {safe, steady, settled, connected: ok|concern}, "note", "photo_ids", "hazard_ids"}
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    checkin_lat: Mapped[float | None] = mapped_column(nullable=True)
    checkin_lng: Mapped[float | None] = mapped_column(nullable=True)
    # Where the visit was logged from (app/livewell/visit_location.py). Null = no location.
    checkin_accuracy_m: Mapped[float | None] = mapped_column(nullable=True)
    checkout_lat: Mapped[float | None] = mapped_column(nullable=True)
    checkout_lng: Mapped[float | None] = mapped_column(nullable=True)
    checkout_accuracy_m: Mapped[float | None] = mapped_column(nullable=True)
    # Repeating visits (app/models/care_series.py): the series and its IST day.
    series_id: Mapped[int | None] = mapped_column(
        ForeignKey("care_series.id", ondelete="SET NULL"), nullable=True, index=True
    )
    series_date: Mapped[date | None] = mapped_column(Date, nullable=True)
