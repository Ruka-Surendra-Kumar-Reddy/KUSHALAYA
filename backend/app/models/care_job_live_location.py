"""Where the caregiver is right now, while they are on the way to a visit.

One row per job, overwritten on each update — no history is kept. The row is
deleted as soon as the job leaves "on the way" (arrived, completed, cancelled,
missed or reassigned). See app/livewell/live_location.py.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CareJobLiveLocation(Base):
    __tablename__ = "care_job_live_locations"

    job_id: Mapped[int] = mapped_column(ForeignKey("care_jobs.id", ondelete="CASCADE"), primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    caregiver_id: Mapped[int | None] = mapped_column(
        ForeignKey("caregivers.id", ondelete="CASCADE"), nullable=True
    )
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Set when a staff member (care manager) shares from the ops web page; their name is shown.
    shared_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
