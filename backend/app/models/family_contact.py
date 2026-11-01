"""Family contact preferences and family questions ("Call me" / "Ask about…").

family_contacts: one row per family member per client — a portal login
(user_id) or a circle contact without a login (email only). Phone, preferred
channel, timezone (many live abroad) and how much they want to hear (level).

family_questions: a family member asks the care team to call or asks about a
visit / KushLife flag. Household-scoped: everyone linked to the client sees the
question and the reply.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin

CONTACT_CHANNELS = ("whatsapp", "sms", "call", "email")
CONTACT_LEVELS = ("everything", "important", "emergencies")
DEFAULT_TIMEZONE = "Asia/Kolkata"


class FamilyContact(TimestampMixin, Base):
    __tablename__ = "family_contacts"
    # One row per login per client, and one per email-only contact per client.
    __table_args__ = (
        Index(
            "uq_family_contacts_elder_user", "elder_id", "user_id", unique=True,
            sqlite_where=text("user_id IS NOT NULL"), postgresql_where=text("user_id IS NOT NULL"),
        ),
        Index(
            "uq_family_contacts_elder_email", "elder_id", "email", unique=True,
            sqlite_where=text("user_id IS NULL"), postgresql_where=text("user_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id"), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    # Circle contacts without a login are keyed by email (lower-case).
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="whatsapp")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default=DEFAULT_TIMEZONE)
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="everything")


class FamilyQuestion(TimestampMixin, Base):
    __tablename__ = "family_questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id"), nullable=False, index=True)
    asker_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # call_me | ask
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    call_window: Mapped[str | None] = mapped_column(String(60), nullable=True)
    visit_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    visit_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    flag_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    replied_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    replied_by_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    done_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
