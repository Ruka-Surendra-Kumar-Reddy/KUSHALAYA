"""A repeating visit: "Mon/Wed/Fri 10:00 for 60 min until 31 Mar" for one client.

Individual CareJobs are materialised about four weeks ahead (see
app/livewell/care_series.py); the jobs timer tops the horizon up. Each job
carries series_id + series_date (its IST day), unique together, so generation
is idempotent and a visit cancelled "this visit only" is never re-created.
"""

from datetime import date

from sqlalchemy import JSON, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class CareSeries(TimestampMixin, Base):
    __tablename__ = "care_series"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), index=True)
    caregiver_id: Mapped[int | None] = mapped_column(
        ForeignKey("caregivers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="Care visit")
    tasks: Mapped[str] = mapped_column(Text, default="")
    # IST weekdays, Monday = 0, comma separated ("0,2,4").
    weekdays: Mapped[str] = mapped_column(String(20), default="")
    time_hm: Mapped[str] = mapped_column(String(5), default="10:00")  # IST "HH:MM"
    duration_minutes: Mapped[int] = mapped_column(default=60)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # inclusive; None = open-ended
    generated_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)  # active | ended
    # The series this one continues after a "this and following" change.
    previous_id: Mapped[int | None] = mapped_column(nullable=True)
    # Visits that could not go to the caregiver: [{date, reason, job_id}] (latest 60).
    clashes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
