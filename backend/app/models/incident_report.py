"""Incident reports (FIX_TODO #97): written after the event — falls, near-misses,
medication errors, complaints, injuries.

Not the same as ``care_incidents`` (live SOS / wearable alerts). A report is filed
by a caregiver on a visit or by staff on the client page, reviewed by the care
manager and closed with an outcome. The family sees only ``family_summary`` and
only once the report is reviewed; ``staff_notes`` never leaves ops.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class IncidentReport(TimestampMixin, Base):
    __tablename__ = "care_incident_reports"
    __table_args__ = (Index("ix_care_incident_reports_elder_status", "elder_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), index=True)
    care_job_id: Mapped[int | None] = mapped_column(ForeignKey("care_jobs.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)  # fall | near_miss | medication_error | complaint | injury | other
    serious: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location: Mapped[str] = mapped_column(String(300), default="")
    what_happened: Mapped[str] = mapped_column(Text, default="")
    injury: Mapped[str] = mapped_column(Text, default="")
    action_taken: Mapped[str] = mapped_column(Text, default="")
    witnesses: Mapped[str] = mapped_column(String(500), default="")
    family_informed: Mapped[bool] = mapped_column(Boolean, default=False)
    family_informed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reported_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reported_by_name: Mapped[str] = mapped_column(String(200), default="")
    reporter_role: Mapped[str] = mapped_column(String(30), default="")
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)  # open | reviewed | closed
    follow_ups: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{id, action, owner, due_date, done}]
    staff_notes: Mapped[str] = mapped_column(Text, default="")
    family_summary: Mapped[str] = mapped_column(Text, default="")
    outcome: Mapped[str] = mapped_column(Text, default="")
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
