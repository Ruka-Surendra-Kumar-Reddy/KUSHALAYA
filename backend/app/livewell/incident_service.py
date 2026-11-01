"""Incident lifecycle — open / acknowledge / escalate / resolve, with an append-only event log.

The ``care_incidents`` row is the source of truth. The legacy JSON mirror on
``elder.custom_attributes.safe_home.family_hub`` is still written so the family
portal keeps working; ``legacy_id`` links the two.

Dedupe rules (server side, so a chatty ingestor cannot flood staff):

* same tenant + elder + kind + ``dedupe_key`` while an incident is still open and
  within ``dedupe_seconds`` (IoT broker settings) → the existing row is returned
  and a ``received`` event notes "duplicate suppressed";
* ``device_offline`` / ``battery_low`` never stack: while one is open for the
  elder, further signals are appended to it and no new family alert is pushed.

Escalation policy (defaults, overridable through the ``incident_escalation``
app-global-setting — a JSON object with the same keys, plus an optional
``tenants`` map keyed by tenant id):

* ``ack_minutes`` (5)    → level 1: email + SMS/WhatsApp to the tenant's
  CARE_MANAGER / TENANT_ADMIN users;
* ``level2_minutes`` (10) → level 2: SMTP_ALERT_TO / TWILIO_ALERT_TO / Telegram;
* ``level3_minutes`` (20) → level 3: repeat level 2 and mark the incident
  ``escalated``.

Acknowledging stops the clock. Every step and every delivery attempt is an
``IncidentEvent``.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rbac import CARE_MANAGER, TENANT_ADMIN
from app.core.responses import raise_bad_request, raise_not_found
from app.models.elder import Elder
from app.models.incident import (
    COLLAPSE_KINDS,
    EVENT_CHANNELS,
    FAMILY_OUTCOME,
    INCIDENT_KINDS,
    INCIDENT_OUTCOMES,
    INCIDENT_SEVERITIES,
    INCIDENT_SOURCES,
    OPEN_STATUSES,
    Incident,
    IncidentEvent,
)
from app.models.user import User
from app.services.notifications import get_email_provider, get_sms_provider, get_whatsapp_provider

logger = logging.getLogger(__name__)

ESCALATION_SETTINGS_KEY = "incident_escalation"
DEFAULT_ESCALATION_POLICY: dict[str, int] = {
    "ack_minutes": 5,
    "level2_minutes": 10,
    "level3_minutes": 20,
}
MAX_ESCALATION_LEVEL = 3
DEFAULT_DEDUPE_SECONDS = 65

STAFF_ESCALATION_ROLES = (CARE_MANAGER, TENANT_ADMIN)

KIND_LABELS = {
    "sos_button": "Wearable SOS",
    "fall": "Possible fall",
    "immobility": "Immobility warning",
    "device_offline": "Wearable offline",
    "battery_low": "Wearable battery low",
    "family_sos": "Family SOS",
    "staff_emergency": "Emergency",
    "other": "Incident",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; treat them as UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _minutes_between(start: datetime | None, end: datetime | None) -> int:
    s = _aware(start)
    e = _aware(end)
    if s is None or e is None:
        return 0
    return max(0, int((e - s).total_seconds() // 60))


def kind_label(kind: str) -> str:
    return KIND_LABELS.get(kind, KIND_LABELS["other"])


# ---------------------------------------------------------------------------
# Policy / settings
# ---------------------------------------------------------------------------


def dedupe_seconds(db: Session) -> int:
    """The IoT broker ``dedupe_seconds`` (same window the ingestor uses for SOS ads)."""
    try:
        from app.livewell.iot_broker_settings import get_broker_settings

        value = int(get_broker_settings(db).get("dedupe_seconds") or DEFAULT_DEDUPE_SECONDS)
        return max(1, value)
    except Exception:  # pragma: no cover — settings table missing in odd dev states
        logger.debug("incident_dedupe_seconds_fallback", exc_info=True)
        return DEFAULT_DEDUPE_SECONDS


CONTACT_KEYS = ("level1_phones", "level2_emails", "level2_phones")


def _merge(base: list[str], extra: list[str]) -> list[str]:
    seen = {x.lower() for x in base}
    return base + [x for x in extra if x.lower() not in seen]


def normalize_alert_phone(raw: str) -> str | None:
    """Indian 10-digit numbers get +91; anything else must already carry its country code."""
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if len(digits) == 10:
        digits = "91" + digits
    return f"+{digits}" if 11 <= len(digits) <= 15 else None


def _escalation_raw(db: Session) -> tuple[Any, dict]:
    from app.models.app_global_setting import AppGlobalSetting

    AppGlobalSetting.__table__.create(bind=db.get_bind(), checkfirst=True)
    row = db.get(AppGlobalSetting, ESCALATION_SETTINGS_KEY)
    return row, (dict(row.value) if row and isinstance(row.value, dict) else {})


def escalation_contacts(db: Session, tenant_id: int | None) -> dict[str, list[str]]:
    """Extra people on the SOS escalation tree for this agency (Settings → SOS escalation)."""
    try:
        _row, raw = _escalation_raw(db)
    except Exception:  # pragma: no cover
        db.rollback()
        raw = {}
    t = (raw.get("tenants") or {}).get(str(tenant_id)) if tenant_id is not None else None
    t = t if isinstance(t, dict) else {}
    return {k: [str(x) for x in t.get(k) or []] for k in CONTACT_KEYS}


def save_escalation_tree(db: Session, tenant_id: int, body: dict) -> dict:
    """Minutes for each step and the extra people, stored per agency."""
    from sqlalchemy.orm.attributes import flag_modified

    from app.models.app_global_setting import AppGlobalSetting

    row, raw = _escalation_raw(db)
    tenants = dict(raw.get("tenants") or {})
    cur = dict(tenants.get(str(tenant_id)) or {})
    for key in DEFAULT_ESCALATION_POLICY:
        if body.get(key) not in (None, ""):
            cur[key] = max(1, min(240, int(body[key])))
    if "level2_emails" in body:
        cur["level2_emails"] = sorted({str(e).strip() for e in body["level2_emails"] or [] if "@" in str(e)})[:20]
    for key in ("level1_phones", "level2_phones"):
        if key in body:
            phones = [normalize_alert_phone(p) for p in body[key] or []]
            cur[key] = sorted({p for p in phones if p})[:20]
    tenants[str(tenant_id)] = cur
    raw["tenants"] = tenants
    if row is None:
        db.add(AppGlobalSetting(key=ESCALATION_SETTINGS_KEY, value=raw))
    else:
        row.value = raw
        flag_modified(row, "value")
    db.commit()
    return escalation_tree(db, tenant_id)


def escalation_tree(db: Session, tenant_id: int) -> dict:
    return {**escalation_policy(db, tenant_id), **escalation_contacts(db, tenant_id)}


def escalation_policy(db: Session, tenant_id: int | None = None) -> dict[str, int]:
    """Defaults merged with the ``incident_escalation`` app setting (+ per-tenant override)."""
    policy = dict(DEFAULT_ESCALATION_POLICY)
    try:
        from app.models.app_global_setting import AppGlobalSetting

        row = db.query(AppGlobalSetting).filter(AppGlobalSetting.key == ESCALATION_SETTINGS_KEY).first()
        raw = row.value if row and isinstance(row.value, dict) else {}
    except Exception:  # pragma: no cover
        db.rollback()
        raw = {}

    def _apply(src: dict) -> None:
        for key in DEFAULT_ESCALATION_POLICY:
            if key in src:
                try:
                    policy[key] = max(1, int(src[key]))
                except (TypeError, ValueError):
                    continue

    _apply(raw)
    tenants = raw.get("tenants") if isinstance(raw.get("tenants"), dict) else {}
    if tenant_id is not None and isinstance(tenants.get(str(tenant_id)), dict):
        _apply(tenants[str(tenant_id)])
    # Keep the ladder monotonic whatever an operator typed.
    policy["level2_minutes"] = max(policy["level2_minutes"], policy["ack_minutes"])
    policy["level3_minutes"] = max(policy["level3_minutes"], policy["level2_minutes"])
    return policy


def target_level_for_elapsed(elapsed_minutes: float, policy: dict[str, int]) -> int:
    if elapsed_minutes >= policy["level3_minutes"]:
        return 3
    if elapsed_minutes >= policy["level2_minutes"]:
        return 2
    if elapsed_minutes >= policy["ack_minutes"]:
        return 1
    return 0


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


def record_event(
    db: Session,
    incident: Incident,
    event: str,
    *,
    channel: str | None = None,
    recipient: str | None = None,
    ok: bool = True,
    detail: str | None = None,
    actor_user_id: int | None = None,
    at: datetime | None = None,
    commit: bool = False,
) -> IncidentEvent:
    if channel is not None and channel not in EVENT_CHANNELS:
        raise ValueError(f"unknown channel {channel!r}")
    row = IncidentEvent(
        incident_id=incident.id,
        at=at or _now(),
        event=event,
        channel=channel,
        recipient=(recipient or None) and str(recipient)[:255],
        ok=bool(ok),
        detail=(detail or None) and str(detail)[:2000],
        actor_user_id=actor_user_id,
    )
    db.add(row)
    if commit:
        db.commit()
    else:
        db.flush()
    return row


def record_notification_attempts(
    db: Session,
    incident: Incident,
    attempts: list[dict[str, Any]],
    *,
    at: datetime | None = None,
    commit: bool = True,
) -> None:
    """Persist one ``notified`` event per delivery attempt (channel, recipient, ok, detail)."""
    for attempt in attempts:
        record_event(
            db,
            incident,
            "notified",
            channel=attempt.get("channel"),
            recipient=attempt.get("recipient"),
            ok=bool(attempt.get("ok")),
            detail=attempt.get("detail"),
            at=at,
        )
    if commit:
        db.commit()


def list_events(db: Session, incident_id: int) -> list[IncidentEvent]:
    return (
        db.query(IncidentEvent)
        .filter(IncidentEvent.incident_id == incident_id)
        .order_by(IncidentEvent.at.asc(), IncidentEvent.id.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# Delivery helpers (return attempt dicts; never raise)
# ---------------------------------------------------------------------------


def _provider_name(value: str | None) -> str:
    return (value or "log").strip().lower()


def deliver_email(recipients: list[str], *, subject: str, text: str, html: str | None) -> list[dict]:
    attempts: list[dict] = []
    if not recipients:
        return attempts
    from app.services.notifications import channel_config

    if _provider_name(settings.NOTIFICATION_EMAIL_PROVIDER) in {"", "log"} and not channel_config.active("email"):
        attempts.append(
            {"channel": "email", "recipient": None, "ok": False, "detail": "skipped: email provider not configured"}
        )
        return attempts
    provider = get_email_provider()
    for to in recipients:
        try:
            result = provider.send(to=to, subject=subject, body=text, html=html)
            attempts.append(
                {"channel": "email", "recipient": to, "ok": bool(result.success), "detail": result.detail}
            )
            if not result.success:
                logger.warning("incident_email_failed to=%s detail=%s", to, result.detail)
        except Exception as exc:  # noqa: BLE001
            logger.exception("incident_email_failed to=%s", to)
            attempts.append({"channel": "email", "recipient": to, "ok": False, "detail": str(exc)[:400]})
    return attempts


def deliver_phone(recipients: list[str], *, body: str) -> list[dict]:
    """SMS and WhatsApp to the same E.164 list (whichever providers are configured)."""
    attempts: list[dict] = []
    if not recipients:
        return attempts
    from app.services.notifications import channel_config

    sms_configured = _provider_name(settings.NOTIFICATION_SMS_PROVIDER) not in {"", "log"} or bool(
        channel_config.active("sms")
    )
    wa_configured = _provider_name(settings.NOTIFICATION_WHATSAPP_PROVIDER) not in {"", "log"}
    if not sms_configured and not wa_configured:
        attempts.append(
            {"channel": "sms", "recipient": None, "ok": False, "detail": "skipped: SMS/WhatsApp provider not configured"}
        )
        return attempts
    if sms_configured:
        sms = get_sms_provider()
        for to in recipients:
            try:
                result = sms.send(to=to, body=body)
                attempts.append({"channel": "sms", "recipient": to, "ok": bool(result.success), "detail": result.detail})
                if not result.success:
                    logger.warning("incident_sms_failed to=%s detail=%s", to, result.detail)
            except Exception as exc:  # noqa: BLE001
                logger.exception("incident_sms_failed to=%s", to)
                attempts.append({"channel": "sms", "recipient": to, "ok": False, "detail": str(exc)[:400]})
    if wa_configured:
        wa = get_whatsapp_provider()
        for to in recipients:
            try:
                result = wa.send_text(to=to, body=body)
                attempts.append(
                    {"channel": "whatsapp", "recipient": to, "ok": bool(result.success), "detail": result.detail}
                )
                if not result.success:
                    logger.warning("incident_whatsapp_failed to=%s detail=%s", to, result.detail)
            except Exception as exc:  # noqa: BLE001
                logger.exception("incident_whatsapp_failed to=%s", to)
                attempts.append({"channel": "whatsapp", "recipient": to, "ok": False, "detail": str(exc)[:400]})
    return attempts


def deliver_telegram(body: str) -> list[dict]:
    from app.services.notifications.telegram_bot import send_telegram_message, telegram_chat_ids

    attempts: list[dict] = []
    if not (settings.TELEGRAM_BOT_TOKEN or "").strip():
        return attempts
    chats = telegram_chat_ids()
    for chat in chats:
        try:
            result = send_telegram_message(body, chat_id=chat)
            attempts.append(
                {"channel": "telegram", "recipient": chat, "ok": bool(result.success), "detail": result.detail}
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("incident_telegram_failed chat=%s", chat)
            attempts.append({"channel": "telegram", "recipient": chat, "ok": False, "detail": str(exc)[:400]})
    return attempts


def phone_alert_recipients() -> list[str]:
    from app.services.notifications.twilio_messaging import to_e164

    seen: set[str] = set()
    out: list[str] = []
    for raw in (settings.TWILIO_ALERT_TO or "").split(","):
        e164 = to_e164(raw.strip())
        if e164 and e164 not in seen:
            seen.add(e164)
            out.append(e164)
    return out


def ops_email_recipients() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in (settings.SMTP_ALERT_TO or "").split(","):
        addr = raw.strip()
        if addr and "@" in addr and addr.lower() not in seen:
            seen.add(addr.lower())
            out.append(addr)
    return out


def staff_email_recipients(db: Session, tenant_id: int) -> list[str]:
    rows = (
        db.query(User)
        .filter(
            User.tenant_id == tenant_id,
            User.role.in_(STAFF_ESCALATION_ROLES),
            User.status == "ACTIVE",
        )
        .order_by(User.id)
        .all()
    )
    seen: set[str] = set()
    out: list[str] = []
    for user in rows:
        addr = (user.email or "").strip()
        if addr and "@" in addr and not addr.lower().endswith(".example") and addr.lower() not in seen:
            seen.add(addr.lower())
            out.append(addr)
    out += [a for a in _alert_extra(db, tenant_id) if a.lower() not in seen]
    return out


def _alert_extra(db: Session, tenant_id: int) -> list[str]:
    """Extra addresses added under Settings → Email notifications → SOS and safety alerts."""
    from app.livewell.email_notifications import get_rules
    from app.models.tenant import Tenant

    try:
        return get_rules(db.get(Tenant, tenant_id))["staff"]["alert"]["extra"]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


def get_incident(db: Session, incident_id: int, *, tenant_id: int | None = None) -> Incident:
    q = db.query(Incident).filter(Incident.id == incident_id)
    if tenant_id is not None:
        q = q.filter(Incident.tenant_id == tenant_id)
    row = q.first()
    if not row:
        raise_not_found("Incident not found")
    return row


def find_by_legacy_id(db: Session, elder_id: int, legacy_id: str | None) -> Incident | None:
    if not legacy_id:
        return None
    return (
        db.query(Incident)
        .filter(Incident.elder_id == elder_id, Incident.legacy_id == str(legacy_id))
        .order_by(Incident.id.desc())
        .first()
    )


def _open_for_elder(db: Session, elder_id: int, kind: str) -> list[Incident]:
    return (
        db.query(Incident)
        .filter(
            Incident.elder_id == elder_id,
            Incident.kind == kind,
            Incident.status.in_(list(OPEN_STATUSES)),
        )
        .order_by(Incident.opened_at.desc(), Incident.id.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def open_incident(
    db: Session,
    *,
    tenant_id: int,
    elder_id: int,
    kind: str,
    severity: str | None = None,
    source: str = "device",
    note: str | None = None,
    device_mac: str | None = None,
    hub_key: str | None = None,
    dedupe_key: str | None = None,
    legacy_id: str | None = None,
    now: datetime | None = None,
    dedupe_window_seconds: int | None = None,
) -> tuple[Incident, bool]:
    """Open an incident, or return the open one this signal belongs to.

    Returns ``(incident, created)``. ``created`` is False when the signal was a
    duplicate (dedupe window) or a repeat of a collapsing kind — callers must
    not push another family alert in that case.
    """
    kind_n = (kind or "other").strip().lower()
    if kind_n not in INCIDENT_KINDS:
        kind_n = "other"
    if source not in INCIDENT_SOURCES:
        source = "device"
    sev = (severity or "").strip().lower()
    if sev not in INCIDENT_SEVERITIES:
        sev = "critical" if kind_n in {"sos_button", "family_sos"} else "warning"
    at = now or _now()

    key = (dedupe_key or "").strip() or None
    if key:
        window = dedupe_window_seconds if dedupe_window_seconds is not None else dedupe_seconds(db)
        for existing in _open_for_elder(db, elder_id, kind_n):
            if existing.tenant_id != tenant_id or existing.dedupe_key != key:
                continue
            opened = _aware(existing.opened_at)
            if opened is not None and (at - opened) <= timedelta(seconds=window):
                record_event(
                    db,
                    existing,
                    "received",
                    detail=f"duplicate suppressed (dedupe_key={key}, window={window}s)",
                    at=at,
                    commit=True,
                )
                return existing, False

    if kind_n in COLLAPSE_KINDS:
        for existing in _open_for_elder(db, elder_id, kind_n):
            if existing.tenant_id != tenant_id:
                continue
            # Two bands on one client are two problems: collapse per device.
            if device_mac and existing.device_mac and existing.device_mac != device_mac:
                continue
            record_event(
                db,
                existing,
                "received",
                detail=f"repeat {kind_label(kind_n).lower()} signal while incident open"
                + (f" — {note.strip()}" if (note or "").strip() else ""),
                at=at,
                commit=True,
            )
            return existing, False

    incident = Incident(
        tenant_id=tenant_id,
        elder_id=elder_id,
        kind=kind_n,
        severity=sev,
        status="open",
        source=source,
        device_mac=(device_mac or None) and str(device_mac)[:32],
        hub_key=(hub_key or None) and str(hub_key)[:64],
        dedupe_key=key and key[:200],
        note=(note or "").strip() or None,
        opened_at=at,
        escalation_level=0,
        legacy_id=(legacy_id or None) and str(legacy_id)[:64],
    )
    db.add(incident)
    db.flush()
    record_event(
        db,
        incident,
        "received",
        detail=f"{kind_label(kind_n)} via {source}" + (f" · mac={device_mac}" if device_mac else ""),
        at=at,
        commit=True,
    )
    return incident, True


def acknowledge(
    db: Session, incident: Incident, user: User, *, now: datetime | None = None, stop_siren: bool = True
) -> Incident:
    if incident.status in {"resolved", "closed"}:
        raise_bad_request("Incident is already resolved")
    at = now or _now()
    if incident.acknowledged_at is None:
        incident.acknowledged_at = at
        incident.acknowledged_by_user_id = user.id
    if incident.status == "open":
        incident.status = "acknowledged"
    from app.livewell import sos_siren

    # Acknowledging on the Alerts page also stops this person's SOS siren.
    if stop_siren:
        sos_siren.mark_acknowledged(db, incident, user, at)
    record_event(
        db,
        incident,
        "acknowledged",
        channel="portal",
        actor_user_id=user.id,
        detail=f"acknowledged by {user.email}",
        at=at,
    )
    db.commit()
    db.refresh(incident)
    # While the family is held back (SOS not yet passed on), tell_family reaches
    # only a family member who pressed it.
    who = (f"{user.first_name or ''}".strip() or "Your care team")
    tell_family(
        db, incident,
        f"{who} has seen the alert",
        f"{who} from your KushAlaya care team saw the {kind_label(incident.kind).lower()} at "
        f"{_ist(at)} and is handling it. We'll update you here.",
    )
    return incident


def add_note(db: Session, incident: Incident, user: User | None, text: str, *, now: datetime | None = None) -> IncidentEvent:
    body = (text or "").strip()
    if not body:
        raise_bad_request("Note required")
    row = record_event(
        db,
        incident,
        "note",
        channel="portal",
        actor_user_id=user.id if user else None,
        detail=body[:2000],
        at=now,
        commit=True,
    )
    return row


def _escalation_message(db: Session, incident: Incident, level: int, now: datetime) -> tuple[str, str, str, str]:
    """(subject, text, html, sms) for an escalation notification."""
    from app.livewell.brand import with_brand
    from app.services.notifications.alert_email import render_iot_alert_email, render_iot_alert_sms

    elder = db.query(Elder).filter(Elder.id == incident.elder_id).first()
    name = f"{elder.first_name} {elder.last_name}".strip() if elder else f"elder #{incident.elder_id}"
    minutes = _minutes_between(incident.opened_at, now)
    title = with_brand(f"{kind_label(incident.kind)} — not acknowledged for {minutes} min")
    subject = with_brand(f"LiveWell360 escalation (step {level}): {kind_label(incident.kind)} — {name}")
    detail_note = (incident.note or "").strip() or None
    text, html = render_iot_alert_email(
        title=title,
        severity=incident.severity,
        client_name=name,
        event_label=kind_label(incident.kind),
        mac_address=incident.device_mac,
        hub_id=incident.hub_key,
        incident_id=incident.legacy_id or str(incident.id),
        status=incident.status,
        note=(f"Nobody has acknowledged this incident for {minutes} minutes. " + (detail_note or "")).strip(),
    )
    sms = render_iot_alert_sms(
        title=title,
        client_name=name,
        hub_id=incident.hub_key,
        mac_address=incident.device_mac,
    )
    return subject, text, html, sms


def notify_escalation_level(db: Session, incident: Incident, level: int, *, now: datetime | None = None) -> list[dict]:
    """Fan out for one escalation level and return the delivery attempts."""
    at = now or _now()
    subject, text, html, sms = _escalation_message(db, incident, level, at)
    attempts: list[dict] = []
    tree = escalation_contacts(db, incident.tenant_id)
    if level <= 1:
        attempts += deliver_email(staff_email_recipients(db, incident.tenant_id), subject=subject, text=text, html=html)
        attempts += deliver_phone(_merge(phone_alert_recipients(), tree["level1_phones"]), body=sms)
    else:
        emails = _merge(ops_email_recipients(), tree["level2_emails"])
        attempts += deliver_email(emails, subject=subject, text=text, html=html)
        attempts += deliver_phone(_merge(phone_alert_recipients(), tree["level2_phones"]), body=sms)
        attempts += deliver_telegram(sms)
    return attempts


def escalate(
    db: Session,
    incident: Incident,
    *,
    level: int | None = None,
    actor_user_id: int | None = None,
    reason: str | None = None,
    now: datetime | None = None,
    notify: bool = True,
    mark_escalated: bool | None = None,
) -> Incident:
    """Raise ``escalation_level`` (to ``level`` or +1), notify and log.

    Staff "escalate now" leaves ``level`` None: the incident goes one level up
    (capped at 3, repeated at 3) and is marked ``escalated``. The scan job passes
    an explicit level; only level 3 changes the status there.
    """
    if incident.status in {"resolved", "closed"}:
        raise_bad_request("Incident is already resolved")
    at = now or _now()
    current = int(incident.escalation_level or 0)
    target = min(MAX_ESCALATION_LEVEL, current + 1) if level is None else max(1, min(MAX_ESCALATION_LEVEL, int(level)))
    if target < current:
        target = current
    incident.escalation_level = target
    incident.escalated_at = at
    should_mark = mark_escalated if mark_escalated is not None else (level is None or target >= MAX_ESCALATION_LEVEL)
    if should_mark:
        incident.status = "escalated"
    who = "staff" if actor_user_id else "escalation scan"
    record_event(
        db,
        incident,
        "escalated",
        channel="portal" if actor_user_id else None,
        actor_user_id=actor_user_id,
        detail=f"level {target} by {who}" + (f" — {reason.strip()}" if (reason or "").strip() else ""),
        at=at,
    )
    db.commit()
    if notify:
        attempts = notify_escalation_level(db, incident, target, now=at)
        record_notification_attempts(db, incident, attempts, at=at, commit=True)
    db.refresh(incident)
    return incident


def resolve(
    db: Session,
    incident: Incident,
    *,
    outcome: str,
    note: str | None = None,
    user: User | None = None,
    by_family: bool = False,
    status: str = "resolved",
    resolved_by_label: str | None = None,
    now: datetime | None = None,
    notify_family: bool = True,
) -> Incident:
    outcome_n = (outcome or "").strip().lower()
    if not outcome_n:
        raise_bad_request("outcome required")
    if incident.kind == "staff_emergency":
        # Only the team closes an emergency, always with an outcome and a note.
        from app.livewell.emergency_service import EMERGENCY_OUTCOMES

        if by_family:
            raise_bad_request("The care team closes an emergency")
        if outcome_n not in EMERGENCY_OUTCOMES:
            raise_bad_request(f"outcome must be one of {', '.join(EMERGENCY_OUTCOMES)}")
        if not (note or "").strip():
            raise_bad_request("A note is required to close an emergency")
    if outcome_n == FAMILY_OUTCOME:
        if not by_family:
            raise_bad_request("outcome family_resolved is reserved for the family portal")
    elif outcome_n not in INCIDENT_OUTCOMES:
        raise_bad_request(f"outcome must be one of {', '.join(INCIDENT_OUTCOMES)}")
    text = (note or "").strip()
    if outcome_n == "other" and not text:
        raise_bad_request("note required when outcome is other")
    status_n = (status or "resolved").strip().lower()
    if status_n not in {"resolved", "closed"}:
        raise_bad_request("status must be resolved or closed")
    if incident.status in {"resolved", "closed"}:
        return incident

    at = now or _now()
    incident.status = status_n
    incident.resolved_at = at
    incident.resolved_by_user_id = user.id if user else None
    # A name, not an email ("Lakshmi (family)"), so timelines and the family read well.
    if user is not None and (not resolved_by_label or "@" in resolved_by_label):
        resolved_by_label = person_label(user)
    incident.resolved_by_label = (resolved_by_label or ("family" if by_family else None))
    incident.outcome = outcome_n
    incident.resolution_note = text or None
    record_event(
        db,
        incident,
        status_n,
        channel="portal",
        actor_user_id=user.id if user else None,
        detail=f"{outcome_n}" + (f" — {text}" if text else "") + (f" (by {incident.resolved_by_label})" if incident.resolved_by_label else ""),
        at=at,
    )
    db.commit()
    _mirror_resolution_to_hub(db, incident)
    db.refresh(incident)
    who = incident.resolved_by_label or "your care team"
    if by_family:
        # Family pressed "We're OK — cancel SOS": the team must know straight away.
        _tell_staff_cancelled(db, incident, who)
    elif not notify_family or incident.kind == "staff_emergency":
        # An emergency's family message is the plain outcome only, never the staff note.
        pass
    else:
        tell_family(
            db, incident,
            "Alert closed",
            f"The {kind_label(incident.kind).lower()} was closed by {_staff_name(db, user) or who} at {_ist(at)}."
            + (f" Note: {text}" if text else "")
            + " Reply in Messages if you still need help.",
        )
    return incident


def _ist(dt: datetime) -> str:
    from app.services.notifications.alert_email import format_alert_time

    return format_alert_time(dt)


def _staff_name(db: Session, user: User | None) -> str:
    if not user:
        return ""
    return f"{user.first_name or ''} {user.last_name or ''}".strip()


def tell_family(db: Session, incident: Incident, title: str, body: str) -> None:
    """SOS updates always reach the family (portal + email), whatever their email choices.

    Before staff tap "Notify family" (owner, 29 Oct) only the family member who
    pressed the SOS hears; if no family member pressed it, nobody does."""
    elder = db.query(Elder).filter(Elder.id == incident.elder_id).first()
    if not elder:
        return
    from app.livewell import sos_siren

    only = None
    if sos_siren.family_held(incident):
        only = sos_siren.family_presser(db, incident)
        if only is None or not (only.email or "").strip():
            return
    try:
        from app.livewell.email_notifications import family_recipients, send
        from app.livewell.family_care_hub import FamilyCareHubService

        FamilyCareHubService._push_alert(
            db, elder, title=title, body=body, severity="info", only_email=only.email if only else None,
        )
        from app.livewell.email_notifications import email_context

        to = [only.email] if only else family_recipients(db, elder, "sos")
        with email_context("/alerts", (elder.first_name or "").strip()):
            send(to, title, body, family=True)
    except Exception:
        logger.exception("sos_family_update_failed incident=%s", incident.id)


def _tell_staff_cancelled(db: Session, incident: Incident, who: str) -> None:
    elder = db.query(Elder).filter(Elder.id == incident.elder_id).first()
    if not elder:
        return
    from app.livewell.email_notifications import email_staff

    name = f"{elder.first_name} {elder.last_name}".strip()
    email_staff(
        db, elder, "alert",
        f"SOS cancelled by family — {name}",
        f"{who} pressed \"We're safe - close SOS\" for {name}. A quick call to confirm all is well is still a good idea.",
    )


def _mirror_resolution_to_hub(db: Session, incident: Incident) -> None:
    """Keep the family-portal JSON in step: resolve the legacy row and mark its alerts read."""
    if not incident.legacy_id:
        return
    from app.livewell.family_care_hub import FamilyCareHubService, _hub, _iso, _save_hub

    elder = db.query(Elder).filter(Elder.id == incident.elder_id).first()
    if not elder:
        return
    hub = _hub(elder)
    found = FamilyCareHubService._resolve_incident_in_hub(
        hub,
        incident.legacy_id,
        status=incident.status if incident.status in ("resolved", "closed") else "resolved",
        resolved_by=incident.resolved_by_label or "staff",
    )
    if not found:
        return
    for alert in hub.get("alerts") or []:
        if isinstance(alert, dict) and str(alert.get("incident_id") or "") == incident.legacy_id and not alert.get("read_at"):
            alert["read_at"] = _iso()
    _save_hub(db, elder, hub)


# ---------------------------------------------------------------------------
# Escalation scan (background job)
# ---------------------------------------------------------------------------


def run_escalation_scan(
    db: Session,
    *,
    now: datetime | None = None,
    tenant_id: int | None = None,
) -> dict[str, Any]:
    """Escalate every unacknowledged incident whose age crosses a policy threshold."""
    at = now or _now()
    q = db.query(Incident).filter(Incident.status.in_(["open", "escalated"]))
    if tenant_id is not None:
        q = q.filter(Incident.tenant_id == tenant_id)
    rows = q.order_by(Incident.opened_at.asc()).all()
    policies: dict[int, dict[str, int]] = {}
    escalated: list[dict[str, Any]] = []
    scanned = 0
    for incident in rows:
        scanned += 1
        if incident.acknowledged_at is not None:
            continue
        policy = policies.get(incident.tenant_id)
        if policy is None:
            policy = escalation_policy(db, incident.tenant_id)
            policies[incident.tenant_id] = policy
        elapsed = _minutes_between(incident.opened_at, at)
        target = target_level_for_elapsed(elapsed, policy)
        if target <= int(incident.escalation_level or 0):
            continue
        try:
            escalate(
                db,
                incident,
                level=target,
                now=at,
                reason=f"{elapsed} min without acknowledgement",
                mark_escalated=target >= MAX_ESCALATION_LEVEL,
            )
            escalated.append({"incident_id": incident.id, "level": target, "elapsed_minutes": elapsed})
        except Exception:  # noqa: BLE001 — one bad row must not stop the scan
            logger.exception("incident_escalation_failed incident=%s", incident.id)
            db.rollback()
    # Staff-raised emergencies are owned from the start (acknowledged on raise),
    # so the ladder above skips them; this escalates the ones left untouched.
    from app.livewell.emergency_service import run_idle_scan

    try:
        idle = run_idle_scan(db, now=at, tenant_id=tenant_id)
    except Exception:  # noqa: BLE001
        logger.exception("emergency_idle_scan_failed")
        db.rollback()
        idle = []
    escalated += idle
    # SOS siren: no staff acknowledgement within 2 minutes -> escalate to the heads.
    from app.livewell import sos_siren

    try:
        escalated += sos_siren.run_escalation(db, now=at, tenant_id=tenant_id)
    except Exception:  # noqa: BLE001
        logger.exception("sos_siren_escalation_failed")
        db.rollback()
    return {"scanned": scanned, "escalated": escalated, "escalated_count": len(escalated)}


# ---------------------------------------------------------------------------
# Read models
# ---------------------------------------------------------------------------


def _user_labels(db: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    out: dict[int, str] = {}
    for u in db.query(User).filter(User.id.in_(list(ids))).all():
        out[u.id] = person_label(u)
    return out


def person_label(u: User) -> str:
    """A person's name for staff screens, never a raw email: "Lakshmi (family)".

    Falls back to the email's first part ("lakshmi.r@…" → "Lakshmi") when no name is on file.
    """
    name = f"{u.first_name or ''} {u.last_name or ''}".strip()
    if not name:
        local = (u.email or "").split("@", 1)[0]
        first = re.split(r"[._+\-\d]+", local)[0] if local else ""
        name = first.capitalize() or "Staff"
    if (u.role or "").upper() == "ELDER_PORTAL":
        name = f"{name} (family)"
    return name


def serialize_event(row: IncidentEvent, users: dict[int, str] | None = None) -> dict[str, Any]:
    return {
        "id": row.id,
        "at": _aware(row.at),
        "event": row.event,
        "channel": row.channel,
        "recipient": row.recipient,
        "ok": bool(row.ok),
        "detail": row.detail,
        "actor_user_id": row.actor_user_id,
        "actor_name": (users or {}).get(row.actor_user_id) if row.actor_user_id else None,
    }


def serialize(
    incident: Incident,
    *,
    elder_name: str | None = None,
    users: dict[int, str] | None = None,
    events: list[IncidentEvent] | None = None,
    now: datetime | None = None,
    elder: Elder | None = None,
) -> dict[str, Any]:
    at = now or _now()
    end = incident.resolved_at if incident.status in ("resolved", "closed") else at
    users = users or {}
    data = {
        "id": incident.id,
        "tenant_id": incident.tenant_id,
        "elder_id": incident.elder_id,
        "elder_name": elder_name,
        "kind": incident.kind,
        "kind_label": kind_label(incident.kind),
        "severity": incident.severity,
        "status": incident.status,
        "source": incident.source,
        "device_mac": incident.device_mac,
        "hub_key": incident.hub_key,
        "dedupe_key": incident.dedupe_key,
        "note": incident.note,
        "opened_at": _aware(incident.opened_at),
        "minutes_open": _minutes_between(incident.opened_at, end),
        "acknowledged_at": _aware(incident.acknowledged_at),
        "acknowledged_by": users.get(incident.acknowledged_by_user_id) if incident.acknowledged_by_user_id else None,
        "escalated_at": _aware(incident.escalated_at),
        "escalation_level": int(incident.escalation_level or 0),
        "resolved_at": _aware(incident.resolved_at),
        "resolved_by": (
            users.get(incident.resolved_by_user_id)
            if incident.resolved_by_user_id and incident.resolved_by_user_id in users
            else incident.resolved_by_label
        ),
        "outcome": incident.outcome,
        "resolution_note": incident.resolution_note,
        "legacy_id": incident.legacy_id,
        "owner_user_id": incident.owner_user_id,
        "owner_name": users.get(incident.owner_user_id) if incident.owner_user_id else None,
        "details": incident.details if isinstance(incident.details, dict) else None,
    }
    from app.livewell import sos_siren

    data["sos"] = sos_siren.summary(incident)
    if elder is not None:
        data.update(_elder_contact(elder))
    if events is not None:
        data["events"] = [serialize_event(e, users) for e in events]
    return data


def _elder_home(elder: Elder) -> dict | None:
    """Saved home pin for the Directions button (staff only; address is already shown)."""
    from sqlalchemy.orm import object_session

    from app.livewell.care_jobs import home_point

    db = object_session(elder)
    return home_point(db, elder.id) if db is not None else None


def _elder_contact(elder: Elder) -> dict[str, Any]:
    """Phone / address / family phone for the alert row (call buttons)."""
    family_phone = (elder.emergency_contact_phone or "").strip() or None
    family_name = (elder.emergency_contact_name or "").strip() or None
    if not family_phone:
        sh = (elder.custom_attributes or {}).get("safe_home") if isinstance(elder.custom_attributes, dict) else None
        phones = sh.get("family_phones") if isinstance(sh, dict) else None
        if isinstance(phones, dict):
            for value in phones.values():
                raw = value.get("phone") if isinstance(value, dict) else value
                if str(raw or "").strip():
                    family_phone = str(raw).strip()
                    break
    return {
        "elder_phone": (elder.phone or "").strip() or None,
        "elder_address": (elder.address or "").strip() or None,
        "elder_home": _elder_home(elder),
        "family_phone": family_phone,
        "family_name": family_name,
    }


def list_for_tenant(
    db: Session,
    tenant_id: int | None,
    *,
    statuses: list[str] | None = None,
    limit: int = 200,
    now: datetime | None = None,
    elder_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    wanted = [s for s in (statuses or list(OPEN_STATUSES)) if s]
    q = db.query(Incident, Elder).join(Elder, Elder.id == Incident.elder_id)
    if tenant_id is not None:
        q = q.filter(Incident.tenant_id == tenant_id)
    if elder_ids is not None:
        q = q.filter(Incident.elder_id.in_(elder_ids or {-1}))
    if wanted:
        q = q.filter(Incident.status.in_(wanted))
    rows = q.order_by(Incident.opened_at.desc(), Incident.id.desc()).limit(max(1, min(limit, 500))).all()
    ids: set[int] = set()
    for inc, _elder in rows:
        if inc.acknowledged_by_user_id:
            ids.add(inc.acknowledged_by_user_id)
        if inc.resolved_by_user_id:
            ids.add(inc.resolved_by_user_id)
        if inc.owner_user_id:
            ids.add(inc.owner_user_id)
    users = _user_labels(db, ids)
    out = [
        serialize(inc, elder_name=f"{elder.first_name} {elder.last_name}".strip(), users=users, now=now, elder=elder)
        for inc, elder in rows
    ]
    # Critical first, then the longest-open.
    sev_rank = {"critical": 0, "warning": 1, "info": 2}
    out.sort(key=lambda r: (r["status"] in ("resolved", "closed"), sev_rank.get(r["severity"], 3), -r["minutes_open"]))
    return out


def detail_for_tenant(db: Session, tenant_id: int | None, incident_id: int, *, now: datetime | None = None) -> dict[str, Any]:
    incident = get_incident(db, incident_id, tenant_id=tenant_id)
    elder = db.query(Elder).filter(Elder.id == incident.elder_id).first()
    events = list_events(db, incident.id)
    ids: set[int] = {e.actor_user_id for e in events if e.actor_user_id}
    if incident.acknowledged_by_user_id:
        ids.add(incident.acknowledged_by_user_id)
    if incident.resolved_by_user_id:
        ids.add(incident.resolved_by_user_id)
    if incident.owner_user_id:
        ids.add(incident.owner_user_id)
    users = _user_labels(db, ids)
    data = serialize(
        incident,
        elder_name=f"{elder.first_name} {elder.last_name}".strip() if elder else None,
        users=users,
        events=events,
        now=now,
        elder=elder,
    )
    if incident.kind == "staff_emergency":
        from app.livewell.emergency_service import partner_links_for

        data["partners"] = partner_links_for(db, incident.id)
    return data


def summary(db: Session, tenant_id: int | None, *, elder_ids: set[int] | None = None) -> dict[str, int]:
    """Open incident counts; ``elder_ids`` limits a care manager to their team (same filter as the list)."""
    q = db.query(Incident).filter(Incident.status.in_(list(OPEN_STATUSES)))
    if tenant_id is not None:
        q = q.filter(Incident.tenant_id == tenant_id)
    if elder_ids is not None:
        q = q.filter(Incident.elder_id.in_(elder_ids or {-1}))
    rows = q.all()
    counts = {"open": 0, "acknowledged": 0, "escalated": 0, "critical": 0, "total": 0}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
        counts["total"] += 1
        if row.severity == "critical":
            counts["critical"] += 1
    return counts
