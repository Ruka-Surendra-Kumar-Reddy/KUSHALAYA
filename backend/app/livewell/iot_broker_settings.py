"""Single source of truth for MinewLink / Mosquitto broker settings (Wearables UI)."""

from __future__ import annotations

import logging
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.responses import raise_bad_request
from app.livewell.global_catalog_store import ensure_app_global_settings_table
from app.models.app_global_setting import AppGlobalSetting

logger = logging.getLogger(__name__)

BROKER_SETTINGS_KEY = "iot_mqtt_broker"
TOPIC_MODE_MINEW = "minew_status"
TOPIC_MODE_LIVEWELL = "livewell_ble"


def _mqtt_runtime() -> Path:
    return Path(
        (getattr(settings, "IOT_MQTT_RUNTIME", None) or "").strip()
        or "/var/lib/safehomeops/mqtt"
    )


def _defaults() -> dict[str, Any]:
    return {
        "broker_host": (settings.IOT_MQTT_PUBLIC_HOST or "ops.kushalaya.com").strip(),
        "broker_port": 8883,
        "tls": True,
        "hub_username": "mg7_home1",
        "hub_password": "",
        "ingestor_username": "livewell_ingestor",
        "ingestor_password": "",
        "ingestor_mqtt_topic": "livewell/homes/+/hubs/+/ble,mg7/+/status,/mg7/+/status",
        "dedupe_seconds": 65,
        "immobility_enabled": True,
        "immobility_minutes": 30,
        "offline_enabled": True,
        "offline_seconds": 180,
        "quiet_period_minutes": 60,
        "active_hours_start": 7,
        "active_hours_end": 21,
        "timezone": "Asia/Kolkata",
        "watch_policy_version": 2,
        "topic_mode": TOPIC_MODE_MINEW,
        "subscribe_topic": "",
        "reply_topic": "",
        "use_shared_hub": True,
        "notes": "Edit here; MinewLink uses hub fields; Apply also syncs the MQTT ingestor.",
    }


def _parse_credentials_app(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip("'").strip('"')
    return out


def load_from_credentials_file() -> dict[str, Any]:
    """Bootstrap from /var/lib/safehomeops/mqtt/.credentials.app when present."""
    creds = _parse_credentials_app(_mqtt_runtime() / ".credentials.app")
    base = _defaults()
    if creds.get("MQTT_PUBLIC_HOST"):
        base["broker_host"] = creds["MQTT_PUBLIC_HOST"]
    if creds.get("MQTT_HUB_USER"):
        base["hub_username"] = creds["MQTT_HUB_USER"]
    if creds.get("MQTT_HUB_PASSWORD"):
        base["hub_password"] = creds["MQTT_HUB_PASSWORD"]
    if creds.get("MQTT_INGESTOR_USER"):
        base["ingestor_username"] = creds["MQTT_INGESTOR_USER"]
    if creds.get("MQTT_INGESTOR_PASSWORD"):
        base["ingestor_password"] = creds["MQTT_INGESTOR_PASSWORD"]
    return base


def _normalize(raw: dict | None) -> dict[str, Any]:
    base = _defaults()
    if not isinstance(raw, dict):
        return base
    for key in base:
        if key in raw and raw[key] is not None:
            base[key] = raw[key]
    base["broker_port"] = int(base.get("broker_port") or 8883)
    base["tls"] = bool(base.get("tls", True))
    base["use_shared_hub"] = bool(base.get("use_shared_hub", True))
    mode = str(base.get("topic_mode") or TOPIC_MODE_MINEW).strip().lower()
    if mode not in {TOPIC_MODE_MINEW, TOPIC_MODE_LIVEWELL}:
        mode = TOPIC_MODE_MINEW
    base["topic_mode"] = mode
    base["hub_username"] = str(base.get("hub_username") or "mg7_home1").strip()
    base["hub_password"] = str(base.get("hub_password") or "")
    base["ingestor_username"] = str(base.get("ingestor_username") or "livewell_ingestor").strip()
    base["ingestor_password"] = str(base.get("ingestor_password") or "")
    default_topic = _defaults()["ingestor_mqtt_topic"]
    topic = str(base.get("ingestor_mqtt_topic") or default_topic).strip().replace("\r", "").replace("\n", "")
    if not topic:
        topic = default_topic
    base["ingestor_mqtt_topic"] = topic
    try:
        raw_dedupe = base.get("dedupe_seconds", 65)
        if raw_dedupe is None or raw_dedupe == "":
            dedupe = 65
        else:
            dedupe = int(raw_dedupe)
    except (TypeError, ValueError):
        dedupe = 65
    if dedupe < 1:
        dedupe = 1
    if dedupe > 3600:
        dedupe = 3600
    base["dedupe_seconds"] = dedupe
    stored_watch_ver = 0
    if isinstance(raw, dict) and raw.get("watch_policy_version") is not None:
        try:
            stored_watch_ver = int(raw["watch_policy_version"])
        except (TypeError, ValueError):
            stored_watch_ver = 0
    base["immobility_enabled"] = bool(base.get("immobility_enabled", True))
    base["offline_enabled"] = bool(base.get("offline_enabled", True))
    try:
        imm = int(base.get("immobility_minutes") if base.get("immobility_minutes") not in (None, "") else 30)
    except (TypeError, ValueError):
        imm = 30
    base["immobility_minutes"] = max(1, min(1440, imm))
    try:
        off = int(base.get("offline_seconds") if base.get("offline_seconds") not in (None, "") else 180)
    except (TypeError, ValueError):
        off = 180
    base["offline_seconds"] = max(30, min(3600, off))
    try:
        quiet = int(base.get("quiet_period_minutes") if base.get("quiet_period_minutes") not in (None, "") else 60)
    except (TypeError, ValueError):
        quiet = 60
    base["quiet_period_minutes"] = max(1, min(1440, quiet))
    try:
        ah_s = int(base.get("active_hours_start") if base.get("active_hours_start") not in (None, "") else 7)
        ah_e = int(base.get("active_hours_end") if base.get("active_hours_end") not in (None, "") else 21)
    except (TypeError, ValueError):
        ah_s, ah_e = 7, 21
    base["active_hours_start"] = max(0, min(23, ah_s))
    base["active_hours_end"] = max(0, min(23, ah_e))
    base["timezone"] = str(base.get("timezone") or "Asia/Kolkata").strip() or "Asia/Kolkata"
    if stored_watch_ver < 2:
        # POC had immobility off and UTC hours; B7 motion is live via accelerometer.
        base["immobility_enabled"] = True
        if str(base.get("timezone") or "").strip().upper() == "UTC":
            base["timezone"] = "Asia/Kolkata"
    base["watch_policy_version"] = 2
    base["broker_host"] = str(base.get("broker_host") or base["broker_host"]).strip()
    base["subscribe_topic"] = str(base.get("subscribe_topic") or "").strip()
    base["reply_topic"] = str(base.get("reply_topic") or "").strip()
    return base


def _read_ingestor_env() -> dict[str, str]:
    """Best-effort: MQTT_TOPIC / IOT_DEDUPE_SECONDS from iot_ingestor.env."""
    candidates = [
        Path("/opt/safehomeops/app/backend/iot_ingestor.env"),
        Path(__file__).resolve().parents[2] / "iot_ingestor.env",
    ]
    out: dict[str, str] = {}
    for path in candidates:
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("MQTT_TOPIC=") and "MQTT_TOPIC" not in out:
                    out["MQTT_TOPIC"] = line.split("=", 1)[1].strip().strip("'").strip('"')
                elif line.startswith("IOT_DEDUPE_SECONDS=") and "IOT_DEDUPE_SECONDS" not in out:
                    out["IOT_DEDUPE_SECONDS"] = line.split("=", 1)[1].strip().strip("'").strip('"')
        except OSError:
            continue
        if out:
            break
    return out


def get_broker_settings(db: Session) -> dict[str, Any]:
    try:
        row = (
            db.query(AppGlobalSetting)
            .filter(AppGlobalSetting.key == BROKER_SETTINGS_KEY)
            .first()
        )
    except (ProgrammingError, OperationalError):
        db.rollback()
        ensure_app_global_settings_table()
        row = (
            db.query(AppGlobalSetting)
            .filter(AppGlobalSetting.key == BROKER_SETTINGS_KEY)
            .first()
        )
    file_creds = load_from_credentials_file()
    env = _read_ingestor_env()
    env_topic = env.get("MQTT_TOPIC") or None
    if row and isinstance(row.value, dict):
        data = _normalize(row.value)
        if not data.get("hub_password") and file_creds.get("hub_password"):
            data["hub_password"] = file_creds["hub_password"]
        if not data.get("ingestor_password") and file_creds.get("ingestor_password"):
            data["ingestor_password"] = file_creds["ingestor_password"]
        if not data.get("ingestor_username"):
            data["ingestor_username"] = file_creds.get("ingestor_username") or "livewell_ingestor"
        single = "livewell/homes/+/hubs/+/ble"
        full = _defaults()["ingestor_mqtt_topic"]
        if data.get("ingestor_mqtt_topic") in ("", single) and env_topic:
            data["ingestor_mqtt_topic"] = env_topic if env_topic != single else full
        elif data.get("ingestor_mqtt_topic") == single:
            data["ingestor_mqtt_topic"] = full
        if "dedupe_seconds" not in row.value and env.get("IOT_DEDUPE_SECONDS"):
            try:
                data["dedupe_seconds"] = int(env["IOT_DEDUPE_SECONDS"])
                data = _normalize(data)
            except ValueError:
                pass
        data["source"] = "app"
        return data

    boot = _normalize(file_creds)
    if env_topic:
        boot["ingestor_mqtt_topic"] = env_topic
    if env.get("IOT_DEDUPE_SECONDS"):
        try:
            boot["dedupe_seconds"] = int(env["IOT_DEDUPE_SECONDS"])
            boot = _normalize(boot)
        except ValueError:
            pass
    boot["source"] = (
        "credentials_file"
        if boot.get("hub_password") or boot.get("ingestor_password")
        else "defaults"
    )
    return boot


def save_broker_settings(db: Session, payload: dict, *, commit: bool = True) -> dict[str, Any]:
    data = _normalize(payload)
    if not data["broker_host"]:
        raise_bad_request("broker_host is required")
    if not data["hub_username"]:
        raise_bad_request("hub_username is required")
    if not data["ingestor_username"]:
        raise_bad_request("ingestor_username is required")
    topic = data["ingestor_mqtt_topic"]
    if len(topic) > 500 or any(c in topic for c in "\n\r"):
        raise_bad_request("ingestor_mqtt_topic is invalid")
    if data["broker_port"] <= 0 or data["broker_port"] > 65535:
        raise_bad_request("broker_port must be 1–65535")

    store = {k: data[k] for k in _defaults()}
    for attempt in (1, 2):
        try:
            row = (
                db.query(AppGlobalSetting)
                .filter(AppGlobalSetting.key == BROKER_SETTINGS_KEY)
                .first()
            )
            if row is None:
                db.add(AppGlobalSetting(key=BROKER_SETTINGS_KEY, value=deepcopy(store)))
            else:
                row.value = deepcopy(store)
            if commit:
                db.commit()
            else:
                db.flush()
            out = _normalize(store)
            out["source"] = "app"
            return out
        except (ProgrammingError, OperationalError) as exc:
            db.rollback()
            if attempt == 1:
                ensure_app_global_settings_table()
                continue
            raise


def mac_compact(mac: str) -> str:
    return re.sub(r"[^0-9a-fA-F]", "", mac or "").upper()


def publish_topic_for_mac(broker: dict[str, Any], mac: str, *, home_key: str = "home1", hub_key: str = "mg7-1") -> str:
    mode = str(broker.get("topic_mode") or TOPIC_MODE_MINEW)
    if mode == TOPIC_MODE_LIVEWELL:
        return f"livewell/homes/{home_key}/hubs/{hub_key}/ble"
    compact = mac_compact(mac)
    if len(compact) != 12:
        return "/mg7/{bandMac}/status"
    return f"/mg7/{compact}/status"


def minewlink_cheat_sheet(db: Session, *, mac_address: str, home_key: str = "home1", hub_key: str = "mg7-1") -> dict[str, Any]:
    broker = get_broker_settings(db)
    topic = publish_topic_for_mac(broker, mac_address, home_key=home_key, hub_key=hub_key)
    return {
        "broker_host": broker["broker_host"],
        "broker_port": int(broker["broker_port"]),
        "tls": bool(broker["tls"]),
        "username": broker["hub_username"],
        "password": broker["hub_password"],
        "topic": topic,
        "subscribe_topic": broker.get("subscribe_topic") or "",
        "reply_topic": broker.get("reply_topic") or "",
        "topic_mode": broker["topic_mode"],
        "source": broker.get("source", "app"),
    }


def ingest_watch_policy(broker: dict[str, Any] | None) -> dict[str, Any]:
    """Subset of broker settings consumed by the MQTT ingestor watch loop."""
    data = _normalize(broker if isinstance(broker, dict) else None)
    return {
        "sos_dedupe_seconds": int(data["dedupe_seconds"]),
        "dedupe_seconds": int(data["dedupe_seconds"]),
        "immobility_enabled": bool(data["immobility_enabled"]),
        "immobility_minutes": int(data["immobility_minutes"]),
        "offline_enabled": bool(data["offline_enabled"]),
        "offline_seconds": int(data["offline_seconds"]),
        "quiet_period_minutes": int(data["quiet_period_minutes"]),
        "active_hours_start": int(data["active_hours_start"]),
        "active_hours_end": int(data["active_hours_end"]),
        "timezone": data["timezone"],
    }


def ensure_shared_hub_acl(db: Session) -> dict[str, Any]:
    """Apply hub + ingestor Mosquitto users (and sync iot_ingestor.env)."""
    from app.livewell.iot_mqtt_provision import apply_broker_mqtt

    broker = get_broker_settings(db)
    return apply_broker_mqtt(broker)
