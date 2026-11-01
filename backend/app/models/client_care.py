"""Phase 4B: one-page client sheet, care plan goals, client risk register, manager handovers.

Conditions, allergies and mobility stay on the ``elders`` row (family "request a change"
already targets those); everything else on the sheet lives here.

``keys_access`` (how to get in: key safe code, watchman, spare key) is staff and
caregiver-on-visit-day only. It is never serialised for family APIs.
"""

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class ClientSheet(TimestampMixin, Base):
    __tablename__ = "client_sheets"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), unique=True, index=True)
    # [{"name": "Metformin", "dose": "500 mg", "times": "Morning, Night"}]
    medicines: Mapped[list | None] = mapped_column(JSON, nullable=True)
    risks: Mapped[str] = mapped_column(Text, default="")
    keys_access: Mapped[str] = mapped_column(Text, default="")
    language: Mapped[str] = mapped_column(String(120), default="")
    doctor_name: Mapped[str] = mapped_column(String(200), default="")
    doctor_phone: Mapped[str] = mapped_column(String(40), default="")
    hospital_name: Mapped[str] = mapped_column(String(200), default="")
    hospital_phone: Mapped[str] = mapped_column(String(40), default="")
    family_preferences: Mapped[str] = mapped_column(Text, default="")
    # Care plan review (linked to the 6-monthly reassessment; see app/livewell/client_care.py).
    care_plan_review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    care_plan_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class CareGoal(TimestampMixin, Base):
    __tablename__ = "care_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), index=True)
    goal: Mapped[str] = mapped_column(Text)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | achieved | paused | stopped
    interventions: Mapped[list | None] = mapped_column(JSON, nullable=True)  # ["Walk 10 min with support daily"]
    progress: Mapped[str] = mapped_column(Text, default="")  # plain words; the family sees this
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ClientRisk(TimestampMixin, Base):
    __tablename__ = "client_risks"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), index=True)
    risk: Mapped[str] = mapped_column(String(300))
    level: Mapped[str] = mapped_column(String(10), default="medium")  # low | medium | high
    mitigation: Mapped[str] = mapped_column(Text, default="")
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="open", index=True)  # open | closed


class HandoverNote(TimestampMixin, Base):
    __tablename__ = "handover_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    elder_id: Mapped[int | None] = mapped_column(ForeignKey("elders.id", ondelete="CASCADE"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(20), default="shift")  # shift | client_move
    from_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    to_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    note: Mapped[str] = mapped_column(Text)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
