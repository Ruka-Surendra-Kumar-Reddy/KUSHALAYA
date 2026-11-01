"""LiveWell IoT MQTT ingestor — MG7 → Mosquitto → LiveWell /api/v1/iot/events.

Minew B7: iBeacon 1/1 = SOS. Immobility uses FFE1 A103 accelerometer deltas (iBeacon 1/2 is always-on).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv

    _backend_dir = Path(__file__).resolve().parent.parent
    load_dotenv(_backend_dir / "iot_ingestor.env", override=False)
    load_dotenv(_backend_dir / ".env", override=False)
except ImportError:
    pass

import httpx

try:
    import paho.mqtt.client as mqtt
except ImportError:  # pragma: no cover
    print("Install paho-mqtt: pip install -r iot_ingestor/requirements.txt", file=sys.stderr)
    raise

from iot_ingestor.band_watch import (
    BandState,
    WatchPolicy,
    evaluate_watch,
    immobility_skip_reason,
    sos_should_post,
)
from iot_ingestor.decode import (
    KIND_SOS,
    extract_b7_signals,
    extract_mac_and_sos,
    normalize_mac,
    parse_hub_ids,
    topic_filters_from_env,
)

logger = logging.getLogger("livewell.iot_ingestor")

MAP_REFRESH_SECONDS = float(os.getenv("IOT_DEVICE_MAP_REFRESH_SECONDS", "30"))
WATCH_SECONDS = float(os.getenv("IOT_WATCH_SECONDS", "60"))
TOPIC_FILTERS = topic_filters_from_env(os.getenv("MQTT_TOPIC"))
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USERNAME", "livewell_ingestor")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TLS = os.getenv("MQTT_TLS", "0").strip() in {"1", "true", "yes"}
LIVEWELL_API_BASE = os.getenv("LIVEWELL_API_BASE", "http://127.0.0.1:8010").rstrip("/")
IOT_INGEST_API_KEY = os.getenv("IOT_INGEST_API_KEY", "")
DEVICE_MAP_RAW = os.getenv("IOT_DEVICE_MAP", "{}")

_device_map_lock = threading.Lock()
_device_map: dict[str, int] = {}
_policy = WatchPolicy.from_dict({"sos_dedupe_seconds": os.getenv("IOT_DEDUPE_SECONDS", "65")})
_bands: dict[str, BandState] = {}
_bands_lock = threading.Lock()
# Throttled "still alive" posts so the API can keep IotDevice.last_seen_at
# (the family Devices card) current without a POST per BLE advertisement.
HEARTBEAT_SECONDS = float(os.getenv("IOT_HEARTBEAT_SECONDS", "300"))
_last_heartbeat_post: dict[str, float] = {}


def _parse_env_device_map() -> dict[str, int]:
    try:
        raw = json.loads(DEVICE_MAP_RAW or "{}")
    except json.JSONDecodeError:
        logger.error("IOT_DEVICE_MAP is not valid JSON")
        return {}
    out: dict[str, int] = {}
    if isinstance(raw, dict):
        for mac, elder_id in raw.items():
            try:
                out[normalize_mac(str(mac))] = int(elder_id)
            except (TypeError, ValueError):
                continue
    return out


def _fetch_api_device_map() -> tuple[dict[str, int], dict]:
    if not IOT_INGEST_API_KEY:
        return {}, {}
    url = f"{LIVEWELL_API_BASE}/api/v1/iot/device-map"
    headers = {"X-IoT-Ingest-Key": IOT_INGEST_API_KEY}
    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.get(url, headers=headers)
        if res.status_code >= 400:
            logger.warning("device-map fetch failed %s %s", res.status_code, res.text[:200])
            return {}, {}
        data = res.json()
        if not isinstance(data, dict):
            return {}, {}
        devices = data.get("devices")
        policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
        out: dict[str, int] = {}
        if isinstance(devices, dict):
            for mac, elder_id in devices.items():
                try:
                    out[normalize_mac(str(mac))] = int(elder_id)
                except (TypeError, ValueError):
                    continue
        return out, policy
    except Exception:  # noqa: BLE001
        logger.exception("device-map fetch error")
        return {}, {}


def refresh_device_map() -> dict[str, int]:
    """Merge API registry (preferred) with optional env overrides; refresh watch policy."""
    global _policy
    merged, policy_raw = _fetch_api_device_map()
    env_map = _parse_env_device_map()
    merged.update(env_map)
    if policy_raw:
        _policy = WatchPolicy.from_dict(policy_raw)
    with _device_map_lock:
        global _device_map
        _device_map = merged
        return dict(_device_map)


def get_device_map() -> dict[str, int]:
    with _device_map_lock:
        return dict(_device_map)


def _map_refresh_loop() -> None:
    while True:
        time.sleep(max(5.0, MAP_REFRESH_SECONDS))
        try:
            m = refresh_device_map()
            logger.info("Refreshed device map (%d bindings)", len(m))
        except Exception:  # noqa: BLE001
            logger.exception("device map refresh failed")


def post_event(event: dict) -> None:
    if not IOT_INGEST_API_KEY:
        logger.error("IOT_INGEST_API_KEY not set; dropping event")
        return
    url = f"{LIVEWELL_API_BASE}/api/v1/iot/events"
    headers = {"X-IoT-Ingest-Key": IOT_INGEST_API_KEY, "Content-Type": "application/json"}
    with httpx.Client(timeout=10.0) as client:
        res = client.post(url, headers=headers, json=event)
        if res.status_code >= 400:
            logger.error("LiveWell ingest failed %s %s", res.status_code, res.text)
        else:
            logger.info("Ingested %s → %s", event.get("event_type"), res.text)


def _event_for(mac: str, event_type: str, *, hub_id: str | None, extra: dict | None = None) -> dict:
    device_map = get_device_map()
    elder_id = device_map.get(mac)
    event = {
        "event_type": event_type,
        "device_id": f"b7-{mac.replace(':', '')[-6:]}",
        "hub_id": hub_id or "unknown",
        "mac_address": mac,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "dedupe_key": f"{mac}:{event_type}",
        "raw_payload": extra or {},
    }
    if elder_id is not None:
        event["elder_id"] = elder_id
    else:
        logger.info("No local map for mac=%s — posting %s for API registry resolve", mac, event_type)
    return event


def _band(mac: str) -> BandState:
    with _bands_lock:
        state = _bands.get(mac)
        if state is None:
            state = BandState(mac=mac)
            _bands[mac] = state
        return state


def handle_message(topic: str, payload_bytes: bytes) -> None:
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.warning("Non-JSON MQTT payload on %s (%d bytes)", topic, len(payload_bytes))
        return

    home_id, hub_id = parse_hub_ids(topic)
    now = time.monotonic()
    signals = extract_b7_signals(payload)
    if not signals:
        # Lab dict {"mac","sos"} still works via extract_mac_and_sos
        mac, is_sos, raw = extract_mac_and_sos(payload)
        if mac:
            signals = [{"mac": mac, "kind": KIND_SOS if is_sos else "seen", "rssi": raw.get("rssi") if isinstance(raw, dict) else None, "row": raw}]

    posted_sos: set[str] = set()
    sos_macs: set[str] = set()
    seen_macs: set[str] = set()
    sos_sig: dict[str, dict] = {}
    batteries: dict[str, int] = {}
    for sig in signals:
        mac = sig["mac"]
        kind = sig["kind"]
        seen_macs.add(mac)
        state = _band(mac)
        state.note_seen(now, hub_id=hub_id, offline_seconds=_policy.offline_seconds)
        if sig.get("battery") is not None:
            batteries[mac] = sig["battery"]
        acc = sig.get("acc")
        if acc:
            if state.note_accelerometer(acc, now):
                logger.debug("Motion mac=%s acc=%s", mac, acc)
        if kind == KIND_SOS:
            sos_macs.add(mac)
            sos_sig[mac] = sig
        else:
            logger.debug("Seen mac=%s kind=%s", mac, kind)

    for mac in seen_macs - sos_macs:
        _band(mac).sos_latched = False

    for mac in seen_macs:
        last = _last_heartbeat_post.get(mac)
        if last is not None and now - last < HEARTBEAT_SECONDS:
            continue
        _last_heartbeat_post[mac] = now
        try:
            event = _event_for(mac, "BAND_SEEN", hub_id=hub_id, extra={"topic": topic})
            if mac in batteries:
                event["battery_level"] = batteries[mac]
            post_event(event)
        except Exception:  # noqa: BLE001
            logger.exception("heartbeat post failed mac=%s", mac)

    for mac in sos_macs:
        if mac in posted_sos:
            continue
        state = _band(mac)
        if not sos_should_post(state, now, _policy):
            logger.debug("SOS session continues mac=%s", mac)
            continue
        posted_sos.add(mac)
        sig = sos_sig[mac]
        extra = {
            "topic": topic,
            "home_id": home_id,
            "kind": KIND_SOS,
            "rssi": sig.get("rssi"),
            "major": sig.get("major"),
            "minor": sig.get("minor"),
            "payload": sig.get("row"),
        }
        post_event(_event_for(mac, "SOS_BUTTON", hub_id=hub_id, extra=extra))


def _watch_loop() -> None:
    while True:
        time.sleep(max(15.0, WATCH_SECONDS))
        now = time.monotonic()
        wall = datetime.now(timezone.utc)
        policy = _policy
        due: list[tuple[BandState, str]] = []
        with _bands_lock:
            for state in list(_bands.values()):
                try:
                    alert = evaluate_watch(state, now, policy, wall_now=wall)
                except Exception:  # noqa: BLE001
                    logger.exception("Watch eval failed mac=%s", state.mac)
                    continue
                if alert:
                    due.append((state, alert))
                elif policy.immobility_enabled and state.last_seen_at is not None:
                    reason = immobility_skip_reason(state, now, policy, wall_now=wall)
                    # Only log “almost due” or hard blockers so the journal stays readable.
                    if reason and (
                        reason.startswith("outside_active_hours")
                        or reason.startswith("no_a103")
                        or reason.startswith("still_for=")
                        or reason == "immobility_disabled"
                        or reason.startswith("already_alerted")
                    ):
                        # still_for: only when past half the threshold
                        if reason.startswith("still_for="):
                            still_s = now - (state.last_motion_at or now)
                            if still_s < (policy.immobility_minutes * 60.0) * 0.5:
                                continue
                        logger.info("Watch skip immobility mac=%s reason=%s", state.mac, reason)
        for state, alert in due:
            logger.info("Watch %s mac=%s", alert, state.mac)
            post_event(_event_for(state.mac, alert, hub_id=state.hub_id, extra={"watch": alert}))


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    device_map = refresh_device_map()
    logger.info(
        "Starting ingestor host=%s:%s topics=%s devices=%d sos_dedupe=%ss immobility=%s offline=%ss",
        MQTT_HOST,
        MQTT_PORT,
        TOPIC_FILTERS,
        len(device_map),
        int(_policy.sos_dedupe_seconds),
        f"{int(_policy.immobility_minutes)}m" if _policy.immobility_enabled else "off",
        int(_policy.offline_seconds) if _policy.offline_enabled else 0,
    )
    threading.Thread(target=_map_refresh_loop, name="iot-device-map", daemon=True).start()
    threading.Thread(target=_watch_loop, name="iot-band-watch", daemon=True).start()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="livewell-iot-ingestor")
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD or None)
    if MQTT_TLS:
        client.tls_set()

    def on_connect(client, userdata, flags, reason_code, properties=None):
        logger.info("MQTT connected rc=%s", reason_code)
        for filt in TOPIC_FILTERS:
            client.subscribe(filt)
            logger.info("Subscribed %s", filt)

    def on_message(client, userdata, msg):
        try:
            handle_message(msg.topic, msg.payload)
        except Exception:
            logger.exception("Failed handling %s", msg.topic)

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()
