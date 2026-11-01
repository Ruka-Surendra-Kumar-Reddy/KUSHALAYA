"""SOS siren: one row per person who must hear an SOS (app/livewell/sos_siren.py).

The row is the person's on-screen notice and siren. ``acknowledged_at`` stops it
for that person; the others see who acknowledged. ``audience`` is ``staff`` or
``family``; a watch SOS gets its family rows only once staff confirm it.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class SosSirenAlert(TimestampMixin, Base):
    __tablename__ = "sos_siren_alerts"
    __table_args__ = (
        UniqueConstraint("incident_id", "user_id", name="uq_sos_siren_incident_user"),
        Index("ix_sos_siren_user_open", "user_id", "acknowledged_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("care_incidents.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    audience: Mapped[str] = mapped_column(String(10), default="staff")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
