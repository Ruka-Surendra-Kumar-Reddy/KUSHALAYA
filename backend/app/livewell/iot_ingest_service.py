"""IoT device ingest (MG7 / B7 → LiveWell care-hub alerts)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rbac import ELDER_PORTAL
from app.core.responses import raise_not_found
from app.livewell.brand import with_brand
from app.livewell.family_alert_text import family_device_alert, strip_device_codes
from app.livewell import incident_service
from app.livewell.family_care_hub import FamilyCareHubService, _hub, _iso, _new_id, _save_hub
from app.livewell.iot_registry_service import IotRegistryService
from app.models.elder import Elder
from app.models.user import User

logger = logging.getLogger(__name__)

_EVENT_UI = {
    "SOS_BUTTON": {
        "kind": "sos",
        "db_kind": "sos_button",
        "prefix": "Wearable SOS",
        "title": "SOS from wearable",
        "severity": "critical",
        "id_prefix": "dsos",
    },
    "FALL_SUSPECTED": {
        "kind": "possible_fall",
        "db_kind": "fall",
        "prefix": "Possible fall (experimental)",
        "title": "Possible fall from wearable",
        "severity": "warning",
        "id_prefix": "dfall",
        "default_note": "Suspected fall — confirm with family / visit. Not a medical-device detection.",
    },
    "IMMOBILITY_WARNING": {
        "kind": "immobility",
        "db_kind": "immobility",
        "prefix": "Immobility warning",
        "title": "No motion from wearable",
        "severity": "warning",
        "id_prefix": "dimm",
        "default_note": "Band is online but the accelerometer has not changed recently during active hours.",
    },
    "DEVICE_OFFLINE": {
        "kind": "device_offline",
        "db_kind": "device_offline",
        "prefix": "Wearable offline",
        "title": "Wearable not heard",
        "severity": "warning",
        "id_prefix": "doff",
        "default_note": "No BLE advertisements from this band recently (gateway/range/battery).",
    },
    "BATTERY_LOW": {
        "kind": "battery_low",
        "db_kind": "battery_low",
        "prefix": "Wearable battery low",
        "title": "Wearable battery low",
        "severity": "warning",
        "id_prefix": "dbat",
        "default_note": "Band reported a low battery - charge or swap it before it goes offline.",
    },
}

SUPPORTED_EVENT_TYPES = frozenset(_EVENT_UI.keys())


class IotIngestService:
    """Create care-hub incidents/alerts from wearable / gateway events."""

    @staticmethod
    def raise_device_event(
        db: Session,
        *,
        event_type: str,
        elder_id: int,
        note: str | None = None,
        device_id: str | None = None,
        hub_id: str | None = None,
        mac_address: str | None = None,
        source: str = "mqtt",
        dedupe_key: str | None = None,
    ) -> dict:
        """Open (or fold into) a DB incident, then mirror it to the family hub JSON.

        The ``care_incidents`` row decides whether this signal is new. A duplicate
        (same dedupe_key inside the broker dedupe window) or a repeat of a
        collapsing kind (offline / battery) is appended to the open incident and
        returns ``duplicate=True`` - no new family alert, no new notifications.
        """
        elder = db.query(Elder).filter(Elder.id == elder_id).first()
        if not elder:
            raise_not_found("Elder not found")

        spec = _EVENT_UI.get(event_type) or _EVENT_UI["SOS_BUTTON"]
        band = IotRegistryService.find_device_by_mac(db, mac_address)
        band_label = (band.label if band and band.label else "").strip() or None
        title = with_brand(spec["title"])
        if band_label and band_label.lower() not in {"b7 band", "b7"}:
            title = with_brand(f"{spec['title']} — {band_label}")

        parts = [spec["prefix"]]
        if band_label:
            parts.append(band_label)
        if device_id:
            parts.append(f"device={device_id}")
        if hub_id:
            parts.append(f"hub={hub_id}")
        if mac_address:
            parts.append(f"mac={mac_address}")
        default_note = spec.get("default_note") or " · ".join(parts)
        body = (note or "").strip() or default_note
        if not (note or "").strip():
            body = " · ".join(parts)
            extra = spec.get("default_note")
            if extra:
                body = f"{body} — {extra}"

        legacy_id = _new_id(spec["id_prefix"])
        row, created = incident_service.open_incident(
            db,
            tenant_id=elder.tenant_id,
            elder_id=elder.id,
            kind=spec.get("db_kind") or "other",
            severity=spec["severity"],
            source="device",
            note=body,
            device_mac=mac_address,
            hub_key=hub_id,
            dedupe_key=dedupe_key,
            legacy_id=legacy_id,
        )
        if not created:
            # Folded into an existing open incident: keep the family hub quiet.
            return {
                "id": row.legacy_id or str(row.id),
                "kind": spec["kind"],
                "note": row.note or body,
                "status": row.status,
                "elder_id": elder.id,
                "created_at": row.opened_at,
                "duplicate": True,
                "incident_db_id": row.id,
            }

        # Families get one plain sentence; device/hub/MAC codes stay on the
        # staff incident row (``row.note``) and the hub incident's own fields.
        family_title, family_body = family_device_alert(
            event_type if event_type in _EVENT_UI else "SOS_BUTTON",
            getattr(elder, "first_name", None),
            last_seen=getattr(band, "last_seen_at", None) if band else None,
        )
        if (note or "").strip():
            family_body = strip_device_codes((note or "").strip())
        hub = _hub(elder)
        incident = {
            "id": legacy_id,
            "kind": spec["kind"],
            "note": family_body,
            "staff_note": body,
            "status": "open",
            "created_at": _iso(),
            "created_by": f"iot:{source}",
            "source": source,
            "event_type": event_type,
            "device_id": device_id,
            "hub_id": hub_id,
            "mac_address": mac_address,
            "band_label": band_label,
            "incident_db_id": row.id,
        }
        # A watch SOS is verified first (C1 SOS siren): staff hear it now as
        # "Watch SOS — verify"; the family alert is held until staff confirm it.
        verify = event_type == "SOS_BUTTON"
        if verify:
            from app.livewell import sos_siren

            sos_siren.start(
                db, row, source="watch", verify=True,
                family_pending={"hub_incident": incident, "title": family_title, "body": family_body},
            )
            title = with_brand("Watch SOS — verify") + (f" — {band_label}" if band_label else "")
        else:
            hub["incidents"] = [incident, *hub["incidents"]][:50]
            _save_hub(db, elder, hub)
            FamilyCareHubService._push_alert(
                db,
                elder,
                title=family_title,
                body=family_body,
                severity=spec["severity"],
                incident_id=incident["id"],
            )
        attempts: list[dict] = []
        attempts += IotIngestService._email_device_alert(
            db,
            elder=elder,
            title=title,
            severity=spec["severity"],
            event_label=spec["prefix"],
            incident=incident,
            note=note,
            staff_only=verify,
        )
        attempts += IotIngestService._sms_whatsapp_device_alert(
            elder=elder,
            title=title,
            incident=incident,
        )
        attempts += IotIngestService._telegram_device_alert(
            elder=elder,
            title=title,
            incident=incident,
        )
        # Every delivery attempt (or the reason none was made) lands on the timeline.
        incident_service.record_notification_attempts(db, row, attempts)
        return {
            "id": incident["id"],
            "kind": incident["kind"],
            "note": body,
            "status": incident["status"],
            "elder_id": elder.id,
            "created_at": datetime.now(timezone.utc),
            "duplicate": False,
            "incident_db_id": row.id,
        }

    @staticmethod
    def _email_recipients(db: Session, elder: Elder, *, staff_only: bool = False) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        extra = (
            settings.SMTP_ALERT_TO
            or settings.SMTP_FROM_EMAIL
            or settings.SMTP_USERNAME
            or ""
        ).strip()
        for raw in extra.split(","):
            addr = raw.strip()
            if addr and "@" in addr and addr.lower() not in seen:
                seen.add(addr.lower())
                out.append(addr)
        if staff_only:
            return out
        attrs = elder.custom_attributes if isinstance(elder.custom_attributes, dict) else {}
        block = attrs.get("safe_home") if isinstance(attrs.get("safe_home"), dict) else {}
        extra_elder = block.get("alert_emails") or []
        if isinstance(extra_elder, str):
            extra_elder = extra_elder.split(",")
        for raw in extra_elder:
            addr = str(raw or "").strip()
            if addr and "@" in addr and addr.lower() not in seen:
                seen.add(addr.lower())
                out.append(addr)
        family = (
            db.query(User)
            .filter(
                User.elder_id == elder.id,
                User.role == ELDER_PORTAL,
                User.status == "ACTIVE",
            )
            .all()
        )
        for user in family:
            addr = (user.email or "").strip()
            if (
                addr
                and "@" in addr
                and not addr.lower().endswith(".example")
                and addr.lower() not in seen
            ):
                seen.add(addr.lower())
                out.append(addr)
        return out

    @staticmethod
    def _email_device_alert(
        db: Session,
        *,
        elder: Elder,
        title: str,
        severity: str,
        event_label: str,
        incident: dict,
        note: str | None,
        staff_only: bool = False,
    ) -> list[dict]:
        """Send the wearable alert email; return one attempt dict per recipient.

        ``staff_only``: a watch SOS waiting to be verified — the client's staff
        and the ops alert addresses, never the family."""
        from app.services.notifications.alert_email import render_iot_alert_email

        from app.livewell.incident_service import _alert_extra

        if staff_only:
            from app.livewell.email_notifications import staff_recipients

            recipients = IotIngestService._email_recipients(db, elder, staff_only=True)
            recipients += [a for a in staff_recipients(db, elder, "alert") if a.lower() not in {r.lower() for r in recipients}]
        else:
            recipients = IotIngestService._email_recipients(db, elder)
        recipients += [a for a in _alert_extra(db, elder.tenant_id) if a.lower() not in {r.lower() for r in recipients}]
        if not recipients:
            return []
        name = f"{elder.first_name} {elder.last_name}".strip()
        subject = f"{title} — {name}" if name else title
        human_note = (note or "").strip() or None
        text, html = render_iot_alert_email(
            title=title,
            severity=severity,
            client_name=name or str(elder.id),
            event_label=event_label,
            device_label=incident.get("band_label"),
            device_id=incident.get("device_id"),
            hub_id=incident.get("hub_id"),
            mac_address=incident.get("mac_address"),
            incident_id=incident.get("id"),
            status=incident.get("status") or "Open",
            note=human_note,
        )
        return incident_service.deliver_email(recipients, subject=subject, text=text, html=html)

    @staticmethod
    def _phone_alert_recipients() -> list[str]:
        from app.services.notifications.twilio_messaging import to_e164

        seen: set[str] = set()
        out: list[str] = []
        extra = (settings.TWILIO_ALERT_TO or "").strip()
        for raw in extra.split(","):
            e164 = to_e164(raw.strip())
            if e164 and e164 not in seen:
                seen.add(e164)
                out.append(e164)
        return out

    @staticmethod
    def _sms_whatsapp_device_alert(
        *,
        elder: Elder,
        title: str,
        incident: dict,
    ) -> list[dict]:
        """SMS + WhatsApp to TWILIO_ALERT_TO; return one attempt dict per delivery."""
        from app.services.notifications.alert_email import render_iot_alert_sms

        recipients = IotIngestService._phone_alert_recipients()
        if not recipients:
            return []
        name = f"{elder.first_name} {elder.last_name}".strip() or str(elder.id)
        body = render_iot_alert_sms(
            title=title,
            client_name=name,
            hub_id=incident.get("hub_id"),
            mac_address=incident.get("mac_address"),
        )
        return incident_service.deliver_phone(recipients, body=body)

    @staticmethod
    def _telegram_device_alert(
        *,
        elder: Elder,
        title: str,
        incident: dict,
    ) -> list[dict]:
        """Telegram to every configured chat; return one attempt dict per chat."""
        from app.services.notifications.alert_email import render_iot_alert_sms

        if not (settings.TELEGRAM_BOT_TOKEN or "").strip():
            return []
        name = f"{elder.first_name} {elder.last_name}".strip() or str(elder.id)
        body = render_iot_alert_sms(
            title=title,
            client_name=name,
            hub_id=incident.get("hub_id"),
            mac_address=incident.get("mac_address"),
        )
        return incident_service.deliver_telegram(body)

    @staticmethod
    def raise_device_sos(
        db: Session,
        *,
        elder_id: int,
        note: str | None = None,
        device_id: str | None = None,
        hub_id: str | None = None,
        mac_address: str | None = None,
        source: str = "mqtt",
        dedupe_key: str | None = None,
    ) -> dict:
        return IotIngestService.raise_device_event(
            db,
            event_type="SOS_BUTTON",
            elder_id=elder_id,
            note=note,
            device_id=device_id,
            hub_id=hub_id,
            mac_address=mac_address,
            source=source,
            dedupe_key=dedupe_key,
        )
