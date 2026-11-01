"""Care incidents (SOS / wearable / family) — the staff-side source of truth.

Historically incidents lived only as JSON on
``elder.custom_attributes["safe_home"]["family_hub"]["incidents"]``. That
mirror is still written (the family portal reads it) but these rows own the
lifecycle: open → acknowledged → escalated → resolved/closed, plus an
append-only event log per incident that records every notification attempt.

Table names are prefixed ``care_`` so they never collide with the elder-care
``incidents`` table other verticals on the shared platform use.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.mixins import TimestampMixin

INCIDENT_KINDS = (
    "sos_button",
    "fall",
    "immobility",
    "device_offline",
    "battery_low",
    "family_sos",
    "staff_emergency",
    "other",
)
INCIDENT_SEVERITIES = ("critical", "warning", "info")
INCIDENT_STATUSES = ("open", "acknowledged", "escalated", "resolved", "closed")
OPEN_STATUSES = frozenset({"open", "acknowledged", "escalated"})
INCIDENT_SOURCES = ("device", "family", "staff")
INCIDENT_OUTCOMES = (
    "contacted_family",
    "contacted_elder",
    "dispatched",
    "false_alarm",
    "device_issue",
    "resolved_home",
    "hospital_admission",
    "other",
)
# Only a family member may close with this outcome (see incident_service.resolve).
FAMILY_OUTCOME = "family_resolved"

EVENT_TYPES = (
    "received",
    "notified",
    "acknowledged",
    "escalated",
    "contacted",
    "resolved",
    "closed",
    "note",
    # Staff-raised emergency process (emergency_service).
    "raised",
    "step",
    "assigned",
    "partner",
)
EVENT_CHANNELS = ("portal", "email", "sms", "whatsapp", "telegram")

# Kinds that must never pile up: a second signal while one is open is appended
# to the existing incident instead of opening another (the "99 identical
# offline alerts" bug).
COLLAPSE_KINDS = frozenset({"device_offline", "battery_low"})


class Incident(TimestampMixin, Base):
    __tablename__ = "care_incidents"
    __table_args__ = (
        Index("ix_care_incidents_tenant_status", "tenant_id", "status"),
        Index("ix_care_incidents_elder_kind_status", "elder_id", "kind", "status"),
        Index("ix_care_incidents_legacy", "legacy_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    elder_id: Mapped[int] = mapped_column(ForeignKey("elders.id"), index=True, nullable=False)

    kind: Mapped[str] = mapped_column(String(40), nullable=False, default="other")
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="warning")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="device")

    device_mac: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hub_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalation_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    # Free-text "who" for resolutions that do not come from a staff user (family email).
    resolved_by_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(40), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The id of the mirrored JSON row in family_hub.incidents (dsos_…, fsos_…, doff_…).
    legacy_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Staff-raised emergency: who owns it until closed, and the emergency details
    # (type, who reported it, reporter phone, raised_by, checklist steps).
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES


class IncidentEvent(Base):
    """Append-only timeline row. There is deliberately no update path."""

    __tablename__ = "care_incident_events"
    __table_args__ = (Index("ix_care_incident_events_incident_at", "incident_id", "at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("care_incidents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event: Mapped[str] = mapped_column(String(20), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recipient: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class IncidentPartnerLink(Base):
    """One emergency partner hand-off: a signed link scoped to one incident.

    Only the SHA-256 of the token is stored; the token itself goes in the email.
    Partner responses are written to the incident timeline as ``partner`` events.
    """

    __tablename__ = "care_incident_partner_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("care_incidents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    partner_name: Mapped[str] = mapped_column(String(200), nullable=False)
    partner_type: Mapped[str] = mapped_column(String(20), nullable=False, default="internal")
    partner_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    partner_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
