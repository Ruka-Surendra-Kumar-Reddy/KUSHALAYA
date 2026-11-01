"""A phone running the KushAlaya Android app, for SOS alarm pushes (app/livewell/push.py).

One row per FCM registration token. The token moves to whoever signed in last on
that phone (register is an upsert on ``token``), so a shared phone never rings
for the previous person.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class PushDevice(TimestampMixin, Base):
    __tablename__ = "push_devices"
    __table_args__ = (Index("ix_push_devices_user", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    token: Mapped[str] = mapped_column(String(512), unique=True)
    platform: Mapped[str] = mapped_column(String(16), default="android")
    # "ops" or "family": which of the two apps the phone runs.
    app: Mapped[str] = mapped_column(String(16), default="ops")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
