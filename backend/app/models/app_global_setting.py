"""Platform-wide key/value JSON settings (not tenant-scoped)."""

from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class AppGlobalSetting(TimestampMixin, Base):
    __tablename__ = "app_global_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
