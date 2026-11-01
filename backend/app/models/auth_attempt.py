"""Sign-in / password-reset attempts, used for brute-force throttling.

DB-backed (not in-process) because production runs uvicorn with several workers.
Rows are short-lived: the throttle prunes anything older than a day.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuthAttempt(Base):
    __tablename__ = "auth_attempts"
    __table_args__ = (Index("ix_auth_attempts_kind_key_at", "kind", "key", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # login_email | login_ip | reset_email
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # Normalised email or client IP — never a password.
    key: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
