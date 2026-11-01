"""Many-to-many: family portal users ↔ elders (multi-senior households)."""

from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin


class FamilyElderLink(TimestampMixin, Base):
    __tablename__ = "family_elder_links"
    __table_args__ = (
        UniqueConstraint("user_id", "elder_id", name="uq_family_elder_links_user_elder"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id"), nullable=False, index=True)
    # One member per elder runs the circle (invites / removes). If nothing is
    # flagged, the oldest link is treated as primary on read.
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    invited_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
