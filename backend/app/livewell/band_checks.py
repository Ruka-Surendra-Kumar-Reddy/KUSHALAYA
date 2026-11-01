"""Wearable band checks run by the job timer, and the "Send test" button on Bands.

* Offline: an active band not heard from for OFFLINE_AFTER.
* Low battery: last reported level at or below LOW_BATTERY.

Each opens a care incident through the normal wearable path (portal alert,
alert email), once per band per kind per India day: the incident's
``dedupe_key`` is ``auto:<kind>:<device id>:<date>``, and we skip a band that
already has one for today or still has an open incident of that kind. Checks
only run in the day (DAY_START..DAY_END IST) so a band charging overnight does
not wake anyone.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.responses import raise_bad_request, raise_not_found
from app.models.elder import Elder
from app.models.incident import OPEN_STATUSES, Incident
from app.models.iot_device import IotDevice

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
OFFLINE_AFTER = timedelta(hours=2)
LOW_BATTERY = 20
DAY_START, DAY_END = 7, 21
_INACTIVE = ("inactive", "archived", "deleted", "discharged")


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _ago(delta: timedelta) -> str:
    mins = int(delta.total_seconds() // 60)
    if mins < 120:
        return f"{mins} min"
    hours = mins // 60
    return f"{hours} h" if hours < 48 else f"{hours // 24} days"


def _already(db: Session, device: IotDevice, kind: str, key: str) -> bool:
    if db.query(Incident.id).filter(Incident.dedupe_key == key).first():
        return True
    return (
        db.query(Incident.id)
        .filter(
            Incident.elder_id == device.elder_id,
            Incident.kind == kind,
            Incident.status.in_(OPEN_STATUSES),
            # One band's open alert must not hide another band on the same client.
            Incident.device_mac == device.mac_address,
        )
        .first()
        is not None
    )


def _raise(db: Session, device: IotDevice, elder: Elder, kind: str, key: str, note: str) -> bool:
    from app.livewell.email_notifications import email_staff, staff_path
    from app.livewell.iot_ingest_service import IotIngestService

    event_type = "DEVICE_OFFLINE" if kind == "device_offline" else "BATTERY_LOW"
    try:
        out = IotIngestService.raise_device_event(
            db,
            event_type=event_type,
            elder_id=elder.id,
            note=note,
            mac_address=device.mac_address,
            source="jobs",
            dedupe_key=key,
        )
    except Exception:
        db.rollback()
        logger.exception("band_check_failed device=%s kind=%s", device.id, kind)
        return False
    if out.get("duplicate"):
        return False
    title = "Band offline" if kind == "device_offline" else "Band battery low"
    email_staff(
        db,
        elder,
        "device",
        title,
        f"{note}\nBand ID: {device.mac_address}.",
        path=staff_path(elder, "devices"),
    )
    return True


def check_bands(db: Session, *, now: datetime | None = None) -> list[str]:
    """Raise offline / low-battery alerts. Returns the dedupe keys raised this run."""
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(IST)
    if not (DAY_START <= local.hour < DAY_END):
        return []
    day = local.date().isoformat()
    raised: list[str] = []
    for device in db.query(IotDevice).filter(IotDevice.status == "active", IotDevice.elder_id.isnot(None)).all():
        elder = db.get(Elder, device.elder_id)
        if not elder or (elder.status or "").lower() in _INACTIVE:
            continue
        name = (elder.first_name or "").strip() or "Your family member"
        seen = _aware(device.last_seen_at)
        # A band never heard from is still being set up: nothing to report yet.
        if seen and now - seen >= OFFLINE_AFTER:
            key = f"auto:device_offline:{device.id}:{day}"
            if not _already(db, device, "device_offline", key):
                note = (
                    f"{name}'s band hasn't been heard from for {_ago(now - seen)}. "
                    "Please check it is worn, charged and near the home hub."
                )
                if _raise(db, device, elder, "device_offline", key, note):
                    raised.append(key)
            continue  # an offline band's battery reading is stale
        if device.battery_level is not None and device.battery_level <= LOW_BATTERY:
            key = f"auto:battery_low:{device.id}:{day}"
            if not _already(db, device, "battery_low", key):
                note = f"{name}'s band battery is at {device.battery_level}%. Please charge it today."
                if _raise(db, device, elder, "battery_low", key, note):
                    raised.append(key)
    return raised


def send_test(db: Session, tenant_id: int, device_id: int) -> dict:
    """"Send test" on Bands: email the people who get this client's safety alerts.
    No incident is opened and the family is not contacted."""
    from app.livewell.email_notifications import email_context, provider_status, send, staff_path, staff_recipients

    device = db.query(IotDevice).filter(IotDevice.id == device_id, IotDevice.tenant_id == tenant_id).first()
    if not device:
        raise_not_found("Band not found")
    if device.elder_id is None:
        raise_bad_request("Give this device to a client first; then a test alert can go to their team.")
    elder = db.get(Elder, device.elder_id)
    if not elder:
        raise_not_found("Client not found")
    to = staff_recipients(db, elder, "alert")
    name = f"{elder.first_name or ''} {elder.last_name or ''}".strip()
    seen = _aware(device.last_seen_at)
    with email_context(staff_path(elder, "devices"), name):
        send(
            to,
            "Test alert (no action needed)",
            f"This is a test from the Bands page for {name}'s band (Band ID {device.mac_address}).\n"
            + (f"Last heard from: {seen.astimezone(IST).strftime('%d %b, %I:%M %p').replace(' 0', ' ')} IST.\n" if seen else "Not heard from yet.\n")
            + (f"Battery: {device.battery_level}%.\n" if device.battery_level is not None else "")
            + "If you got this email, SOS alerts for this client will reach you too.",
            family=False,
        )
    status = provider_status()
    return {"ok": True, "sent_to": to, "email_connected": bool(status.get("connected"))}
