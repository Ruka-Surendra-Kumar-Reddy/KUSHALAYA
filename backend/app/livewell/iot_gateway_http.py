"""Device events in: the MQTT ingestor's POSTs and Minew gateways' HTTP uploads.

Two ways in, one set of rules:

* ``accept_device_event`` — one decoded event (SOS / immobility / offline /
  battery / heartbeat). ``POST /api/v1/iot/events`` (MQTT ingestor) and the HTTP
  gateway path both end here, so routing into incidents is identical.
* ``process_gateway_upload`` — a raw Minew G1 / MG3 HTTP scan batch. Decoded by
  the same ``iot_ingestor.decode`` + ``band_watch`` code the MQTT ingestor runs;
  the per-band watch state lives on the ``iot_devices`` row instead of memory.

Only registered devices count; a device not given to a client is heard (last
seen, battery) but never raises an alert.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from iot_ingestor.band_watch import BandState, WatchPolicy, evaluate_watch, sos_should_post
from iot_ingestor.decode import (
    KIND_SOS,
    extract_b7_signals,
    extract_mac_and_sos,
    gateway_mac_of,
    normalize_mac as _loose_mac,
)

from app.livewell.iot_registry_service import IotRegistryService, device_kind
from app.models.iot_device import IotDevice, IotHub

logger = logging.getLogger(__name__)

ALERT_EVENT_TYPES = frozenset(
    {"SOS_BUTTON", "FALL_SUSPECTED", "IMMOBILITY_WARNING", "DEVICE_OFFLINE", "BATTERY_LOW"}
)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _open_same_device(db: Session, elder_id: int, kind: str, mac: str | None):
    from app.models.incident import OPEN_STATUSES, Incident

    q = db.query(Incident).filter(
        Incident.elder_id == elder_id,
        Incident.kind == kind,
        Incident.status.in_(list(OPEN_STATUSES)),
    )
    if mac:
        q = q.filter(Incident.device_mac == mac)
    return q.order_by(Incident.id.desc()).first()


def accept_device_event(
    db: Session,
    *,
    event_type: str,
    mac_address: str | None,
    elder_id: int | None = None,
    device_id: str | None = None,
    hub_id: str | None = None,
    occurred_at: datetime | None = None,
    battery_level: int | None = None,
    note: str | None = None,
    raw_payload: dict | None = None,
    dedupe_key: str | None = None,
    source: str = "mqtt",
) -> dict:
    """Route one device event. Returns {accepted, incident_id, duplicate, detail}."""
    from app.livewell import incident_service
    from app.livewell.iot_activity_log import log_iot_ingest_for_elder, log_iot_ingest_ignored
    from app.livewell.iot_ingest_service import IotIngestService

    et = (event_type or "").strip().upper()
    # Anything but "offline" proves the device was heard (family Devices card).
    if et != "DEVICE_OFFLINE" and mac_address:
        IotRegistryService.touch_device_seen(
            db,
            mac_address=mac_address,
            battery_level=battery_level,
            seen_at=occurred_at,
            hub_key=hub_id,
        )
    if et not in ALERT_EVENT_TYPES:
        log_iot_ingest_ignored(
            db,
            event_type=et,
            mac_address=mac_address,
            raw_payload=raw_payload,
            detail=f"ignored event_type={et}",
        )
        return {"accepted": True, "detail": f"ignored event_type={et}"}

    device = IotRegistryService.find_device_by_mac(db, mac_address) if mac_address else None
    if device is not None:
        # The registry decides who a device belongs to; unassigned = nobody.
        if device.elder_id is None:
            return {"accepted": False, "detail": "device not assigned to a client"}
        elder_id = int(device.elder_id)
    elif not elder_id or elder_id <= 0:
        return {"accepted": False, "detail": "unknown device"}

    mac_n = device.mac_address if device else (_loose_mac(mac_address) if mac_address else None)

    if et == "IMMOBILITY_WARNING":
        # Still not moving and staff already have it open: no second alert.
        open_row = _open_same_device(db, int(elder_id), "immobility", mac_n)
        if open_row is not None:
            incident_service.record_event(
                db, open_row, "received", detail="still no movement (repeat signal)", commit=True
            )
            return {
                "accepted": True,
                "incident_id": open_row.legacy_id or str(open_row.id),
                "duplicate": True,
                "detail": "folded into open incident",
            }

    result = IotIngestService.raise_device_event(
        db,
        event_type=et,
        elder_id=int(elder_id),
        note=note,
        device_id=device_id,
        hub_id=hub_id,
        mac_address=mac_n or mac_address,
        source=source,
        dedupe_key=dedupe_key,
    )
    if result.get("duplicate"):
        return {
            "accepted": True,
            "incident_id": result["id"],
            "duplicate": True,
            "detail": "folded into open incident",
        }
    log_iot_ingest_for_elder(
        db,
        elder_id=int(elder_id),
        event_type=et,
        mac_address=mac_n or mac_address,
        hub_id=hub_id,
        device_id=device_id,
        incident_id=result["id"],
        note=note,
        raw_payload=raw_payload,
    )
    return {"accepted": True, "incident_id": result["id"], "duplicate": False}


# ----- HTTP gateway uploads -----


def _ts(dt: datetime | None) -> float | None:
    a = _aware(dt)
    return a.timestamp() if a else None


def _dt(ts: float | None) -> datetime | None:
    return datetime.fromtimestamp(ts, tz=timezone.utc) if ts is not None else None


def _parse_xyz(text: str | None) -> tuple[int, int, int] | None:
    try:
        x, y, z = (int(p) for p in (text or "").split(","))
        return x, y, z
    except (TypeError, ValueError):
        return None


def state_from_row(device: IotDevice) -> BandState:
    """The persisted watch state as the ingestor's in-memory BandState."""
    return BandState(
        mac=device.mac_address,
        first_seen_at=_ts(device.last_seen_at),
        last_seen_at=_ts(device.last_seen_at),
        last_motion_at=_ts(device.last_motion_at),
        last_acc=_parse_xyz(device.motion_xyz),
        last_sos_at=_ts(device.sos_active_at),
        sos_latched=device.sos_active_at is not None,
        last_immobility_alert_at=_ts(device.immobility_alerted_at),
    )


def state_to_row(state: BandState, device: IotDevice) -> None:
    device.last_seen_at = _dt(state.last_seen_at)
    device.last_motion_at = _dt(state.last_motion_at)
    device.motion_xyz = ",".join(str(v) for v in state.last_acc) if state.last_acc else None
    device.sos_active_at = _dt(state.last_sos_at) if state.sos_latched else None
    device.immobility_alerted_at = _dt(state.last_immobility_alert_at)


def watch_policy(db: Session) -> WatchPolicy:
    from app.livewell.iot_broker_settings import get_broker_settings, ingest_watch_policy

    try:
        return WatchPolicy.from_dict(ingest_watch_policy(get_broker_settings(db)))
    except Exception:  # noqa: BLE001
        logger.exception("watch_policy_fallback")
        return WatchPolicy()


def _signals(payload: Any) -> list[dict]:
    signals = extract_b7_signals(payload)
    if signals:
        return signals
    # Lab / minimal dict {"mac": ..., "sos": true}
    mac, is_sos, raw = extract_mac_and_sos(payload)
    if mac:
        return [{"mac": mac, "kind": KIND_SOS if is_sos else "seen", "rssi": None, "acc": None, "battery": None, "row": raw}]
    return []


def process_gateway_upload(
    db: Session,
    hub: IotHub,
    payload: Any,
    *,
    now: datetime | None = None,
    policy: WatchPolicy | None = None,
) -> dict:
    """Handle one Minew HTTP scan batch from ``hub``. Returns a small summary."""
    when = _aware(now) or datetime.now(timezone.utc)
    t = when.timestamp()
    pol = policy or watch_policy(db)

    hub.last_seen_at = when
    gw_mac = gateway_mac_of(payload)
    if gw_mac and not hub.mac_address:
        hub.mac_address = gw_mac

    # Group the batch per MAC: a band rotates frames (iBeacon, A103, info).
    grouped: dict[str, dict] = {}
    for sig in _signals(payload):
        g = grouped.setdefault(sig["mac"], {"sos": False, "accs": [], "rssi": None, "battery": None, "row": None})
        if sig.get("kind") == KIND_SOS:
            g["sos"] = True
            g["row"] = sig.get("row")
        if sig.get("acc"):
            g["accs"].append(tuple(sig["acc"]))
        if sig.get("rssi") is not None:
            g["rssi"] = sig["rssi"]
        if sig.get("battery") is not None:
            g["battery"] = sig["battery"]

    devices = []
    if grouped:
        devices = (
            db.query(IotDevice)
            .filter(
                IotDevice.tenant_id == hub.tenant_id,
                IotDevice.status == "active",
                IotDevice.mac_address.in_(list(grouped.keys())),
            )
            .all()
        )
    summary = {"heard": len(grouped), "registered": len(devices), "events": []}
    due: list[tuple[IotDevice, str, dict]] = []
    for device in devices:
        g = grouped[device.mac_address]
        state = state_from_row(device)
        state.note_seen(t, hub_id=hub.hub_key, offline_seconds=pol.offline_seconds)
        for acc in g["accs"]:
            state.note_accelerometer(acc, t)
        if g["sos"]:
            if sos_should_post(state, t, pol):
                due.append((device, "SOS_BUTTON", {"kind": KIND_SOS, "rssi": g["rssi"], "payload": g["row"]}))
        else:
            state.sos_latched = False
        if device.elder_id is not None and device_kind(device.device_type) == "watch":
            alert = evaluate_watch(state, t, pol, wall_now=when)
            if alert == "IMMOBILITY_WARNING":
                due.append((device, alert, {"watch": alert}))
        state_to_row(state, device)
        if g["battery"] is not None:
            device.battery_level = max(0, min(100, int(g["battery"])))
        if g["rssi"] is not None:
            device.last_rssi = int(g["rssi"])
        if device.hub_id is None:
            device.hub_id = hub.id
    db.commit()

    for device, event_type, extra in due:
        if device.elder_id is None:
            continue  # heard, but not given to anyone: never alerts
        compact = device.mac_address.replace(":", "")
        try:
            out = accept_device_event(
                db,
                event_type=event_type,
                mac_address=device.mac_address,
                device_id=f"b7-{compact[-6:]}",
                hub_id=hub.hub_key,
                occurred_at=when,
                raw_payload={"via": "http", **extra},
                dedupe_key=f"{device.mac_address}:{event_type}",
                source="http",
            )
        except Exception:  # noqa: BLE001 — one bad alert must not drop the batch
            db.rollback()
            logger.exception("gateway_http_event_failed mac=%s type=%s", device.mac_address, event_type)
            continue
        summary["events"].append({"mac": device.mac_address, "event_type": event_type, **out})
    return summary
