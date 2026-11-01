"""Minew MG7 / B7 MQTT payload decode (gateway batch + iBeacon SOS)."""

from __future__ import annotations

import re
from typing import Any

# BeaconSET LiveWell UUID (SOS 1/1, optional always-on 1/2 slot).
LIVEWELL_IBEACON_UUID = bytes.fromhex("FDA50693A4E24FB1AFCFC6EB07647825")
# Euclidean Δ² on A103 XYZ; rest jitter is ~10–50, a wrist move is thousands.
ACC_MOTION_DELTA_SQ = 3600


def normalize_mac(mac: str) -> str:
    cleaned = re.sub(r"[^0-9a-fA-F]", "", mac or "").lower()
    if len(cleaned) != 12:
        return (mac or "").strip().lower()
    return ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))


def _ad_structures(raw_data: str | None) -> list[tuple[int, bytes]]:
    if not raw_data or not isinstance(raw_data, str):
        return []
    hex_str = re.sub(r"[^0-9a-fA-F]", "", raw_data)
    if len(hex_str) < 8 or len(hex_str) % 2:
        return []
    try:
        data = bytes.fromhex(hex_str)
    except ValueError:
        return []
    out: list[tuple[int, bytes]] = []
    i = 0
    while i + 1 < len(data):
        length = data[i]
        if length < 1 or i + 1 + length > len(data):
            break
        ad_type = data[i + 1]
        ad_data = data[i + 2 : i + 1 + length]
        out.append((ad_type, ad_data))
        i += 1 + length
    return out


def parse_ibeacon_major_minor(raw_data: str | None) -> tuple[int | None, int | None]:
    """Extract iBeacon major/minor from Apple manufacturer data or Minew UUID service data."""
    for ad_type, ad_data in _ad_structures(raw_data):
        # Manufacturer Specific (0xFF): Apple (4C 00) + iBeacon (02 15) + UUID16 + maj2 + min2 + tx1
        if ad_type == 0xFF and len(ad_data) >= 25 and ad_data[0:4] == b"\x4c\x00\x02\x15":
            major = int.from_bytes(ad_data[20:22], "big")
            minor = int.from_bytes(ad_data[22:24], "big")
            return major, minor
        # Service Data (0x16): 16-byte UUID + major + minor (Minew F1FF copy of the same slot)
        if ad_type == 0x16 and len(ad_data) >= 20 and ad_data[0:16] == LIVEWELL_IBEACON_UUID:
            major = int.from_bytes(ad_data[16:18], "big")
            minor = int.from_bytes(ad_data[18:20], "big")
            return major, minor
    return None, None


def parse_minew_acc(raw_data: str | None) -> tuple[int, int, int] | None:
    """Minew FFE1 A103 accelerometer: signed int16 BE X/Y/Z."""
    for ad_type, ad_data in _ad_structures(raw_data):
        if ad_type != 0x16 or len(ad_data) < 11 or ad_data[0:4] != b"\xe1\xff\xa1\x03":
            continue
        x = int.from_bytes(ad_data[5:7], "big", signed=True)
        y = int.from_bytes(ad_data[7:9], "big", signed=True)
        z = int.from_bytes(ad_data[9:11], "big", signed=True)
        return x, y, z
    return None


def acc_delta_is_motion(
    prev: tuple[int, int, int] | None,
    current: tuple[int, int, int],
    *,
    delta_sq: int = ACC_MOTION_DELTA_SQ,
) -> bool:
    """True when XYZ changed enough vs the previous A103 sample (not first-seen)."""
    if prev is None:
        return False
    dist = sum((a - b) ** 2 for a, b in zip(current, prev, strict=True))
    return dist >= delta_sq


# Field names differ between Minew firmware (MG7/MG3 MQTT, G1 HTTP "JSON-RAW" /
# "JSON-LONG", lab scripts). Accept them all.
_MAC_KEYS = ("mac", "macAddress", "mac_address", "deviceMac", "device_mac", "bleMac", "addr")
_RAW_KEYS = ("rawData", "raw_data", "raw", "advData", "adv_data", "advertisement", "data")
_BATTERY_KEYS = ("battery", "batt", "battery_level", "batteryLevel", "electricity", "power")
_ENVELOPE_KEYS = ("devices", "data", "ble", "items", "objects", "beacons", "list")


def row_mac(row: dict) -> str | None:
    for key in _MAC_KEYS:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def row_raw(row: dict) -> str | None:
    for key in _RAW_KEYS:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None or value == "" or isinstance(value, bool):
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_minew_battery(raw_data: str | None) -> int | None:
    """Battery % from a Minew FFE1 frame: A1 03 (accelerometer) or A1 08 (info)."""
    for ad_type, ad_data in _ad_structures(raw_data):
        if ad_type != 0x16 or len(ad_data) < 5 or ad_data[0:2] != b"\xe1\xff" or ad_data[2] != 0xA1:
            continue
        if ad_data[3] in (0x03, 0x08) and 0 <= ad_data[4] <= 100:
            return ad_data[4]
    return None


def row_battery(row: dict, raw_data: str | None = None) -> int | None:
    """Battery % from parsed gateway fields, else from the Minew raw frame."""
    for key in _BATTERY_KEYS:
        level = _int_or_none(row.get(key))
        if level is not None and 0 <= level <= 100:
            return level
    return parse_minew_battery(raw_data if raw_data is not None else row_raw(row))


def row_acc(row: dict, raw_data: str | None = None) -> tuple[int, int, int] | None:
    """A103 XYZ from raw data, else from parsed xAxis/yAxis/zAxis (G1 JSON-LONG).

    Parsed values in g (|v| <= 16 with decimals, e.g. 0.98) are scaled to the raw
    8.8 units the motion threshold uses, so both formats need the same move.
    """
    acc = parse_minew_acc(raw_data if raw_data is not None else row_raw(row))
    if acc is not None:
        return acc
    for kx, ky, kz in (("xAxis", "yAxis", "zAxis"), ("accX", "accY", "accZ"), ("x", "y", "z")):
        vals = [row.get(kx), row.get(ky), row.get(kz)]
        if any(v is None or isinstance(v, bool) for v in vals):
            continue
        try:
            nums = [float(v) for v in vals]
        except (TypeError, ValueError):
            continue
        if all(abs(n) <= 16 for n in nums) and any(n != int(n) for n in nums):
            nums = [n * 256 for n in nums]
        return int(nums[0]), int(nums[1]), int(nums[2])
    return None


def row_major_minor(row: dict, raw_data: str | None = None) -> tuple[int | None, int | None]:
    """iBeacon major/minor from raw data, else from parsed gateway fields."""
    major, minor = parse_ibeacon_major_minor(raw_data if raw_data is not None else row_raw(row))
    if major is not None and minor is not None:
        return major, minor
    for kmaj, kmin in (("ibeaconMajor", "ibeaconMinor"), ("major", "minor"), ("beaconMajor", "beaconMinor")):
        maj, mnr = _int_or_none(row.get(kmaj)), _int_or_none(row.get(kmin))
        if maj is not None and mnr is not None:
            return maj, mnr
    return None, None


def unwrap_rows(payload: Any) -> list[dict]:
    """The advertisement rows in a gateway upload (bare list, or wrapped in a dict)."""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in _ENVELOPE_KEYS:
            nested = payload.get(key)
            if isinstance(nested, list):
                return [x for x in nested if isinstance(x, dict)]
        return [payload]
    return []


def gateway_mac_of(payload: Any) -> str | None:
    """The uploading gateway's own MAC, when the batch carries it."""
    if isinstance(payload, dict):
        for key in ("gatewayMac", "gateway_mac", "gmac", "gw_mac", "gateway"):
            value = payload.get(key)
            if isinstance(value, str) and len(re.sub(r"[^0-9a-fA-F]", "", value)) == 12:
                return normalize_mac(value)
    for row in unwrap_rows(payload):
        if str(row.get("type") or "").lower() == "gateway" and row_mac(row):
            return normalize_mac(str(row_mac(row)))
    return None


def _explicit_sos_flags(obj: dict) -> bool:
    return bool(
        obj.get("sos")
        or obj.get("SOS")
        or obj.get("button")
        or obj.get("event") in ("SOS", "SOS_BUTTON", "RADAR_FALL_DETECTED")
        or str(obj.get("eventType") or "").upper() == "SOS_BUTTON"
        or str(obj.get("type") or "").upper() in {"SOS", "BUTTON", "ALARM"}
        or str(obj.get("event") or "").upper() in {"SOS", "SOS_BUTTON"}
    )


KIND_SOS = "sos"
KIND_MOTION = "motion"
KIND_SEEN = "seen"


def classify_ibeacon(raw_data: str | None) -> str | None:
    """Map iBeacon: 1/1 SOS. Major 1/2 is an always-on slot on B7 — not a motion event."""
    major, minor = parse_ibeacon_major_minor(raw_data)
    if major is None or minor is None:
        return None
    if major == 1 and minor == 1:
        return KIND_SOS
    return KIND_SEEN


def _ibeacon_sos(raw_data: str | None) -> bool:
    """Minew B7: SOS advertises major=1, minor=1; idle is major=0, minor=0."""
    return classify_ibeacon(raw_data) == KIND_SOS


def classify_ble_row(row: dict) -> tuple[str | None, str | None]:
    """Return (mac, kind) for one MG7 BLE advertisement row (skip Gateway header)."""
    if str(row.get("type") or "").lower() == "gateway":
        return None, None
    mac = row_mac(row)
    if not mac:
        return None, None
    major, minor = row_major_minor(row)
    kind = None
    if major is not None and minor is not None:
        kind = KIND_SOS if (major, minor) == (1, 1) else KIND_SEEN
    if _explicit_sos_flags(row):
        kind = KIND_SOS
    if kind is None:
        kind = KIND_SEEN
    return normalize_mac(str(mac)), kind


def _scan_ble_row(row: dict) -> tuple[str | None, bool, dict | None]:
    """Return (mac, is_sos, preferred_raw_row) for one gateway list element."""
    if str(row.get("type") or "").lower() == "gateway":
        return None, False, None
    mac = row_mac(row)
    if not mac:
        return None, False, None
    sos = _explicit_sos_flags(row) or row_major_minor(row) == (1, 1)
    return normalize_mac(str(mac)), sos, row if sos else None


def extract_mac_and_sos(payload: Any) -> tuple[str | None, bool, dict]:
    """Decode lab dicts and Minew MG7 batch arrays.

    Returns (mac, is_sos, raw_for_meta). For SOS hits, ``raw_for_meta`` prefers the
    BLE advertisement row (includes rssi) rather than the whole batch.
    """
    # Minew publishes a JSON array: [Gateway status, …BLE ads…]
    if isinstance(payload, list):
        first_mac: str | None = None
        for item in payload:
            if not isinstance(item, dict):
                continue
            mac, sos, row = _scan_ble_row(item)
            if mac and first_mac is None:
                first_mac = mac
            if mac and sos and row is not None:
                meta = {
                    "mac": mac,
                    "rssi": row.get("rssi"),
                    "rawData": row.get("rawData"),
                    "timestamp": row.get("timestamp"),
                    "major_minor": parse_ibeacon_major_minor(
                        row.get("rawData") if isinstance(row.get("rawData"), str) else None
                    ),
                    "batch": payload,
                }
                return mac, True, meta
        return first_mac, False, {"_raw": payload}

    if not isinstance(payload, dict):
        return None, False, {"_raw": payload}

    mac = payload.get("mac") or payload.get("macAddress") or payload.get("mac_address")
    sos = _explicit_sos_flags(payload)
    if isinstance(payload.get("rawData"), str) and _ibeacon_sos(payload.get("rawData")):
        sos = True

    devices = payload.get("devices") or payload.get("data") or payload.get("ble")
    if isinstance(devices, list):
        for d in devices:
            if not isinstance(d, dict):
                continue
            d_mac, d_sos, _ = _scan_ble_row(d)
            if d_mac and d_sos:
                return d_mac, True, payload
            if d_mac and not mac:
                mac = d_mac

    if mac:
        return normalize_mac(str(mac)), sos, payload
    return None, sos, payload


def extract_b7_signals(payload: Any) -> list[dict[str, Any]]:
    """Classify each B7 advertisement in a Minew batch or lab dict.

    Each item: mac, kind (sos|motion|seen), rssi, major, minor, row.
    """
    out: list[dict[str, Any]] = []
    for row in unwrap_rows(payload):
        mac, kind = classify_ble_row(row)
        if not mac or not kind:
            continue
        raw_str = row_raw(row)
        major, minor = row_major_minor(row, raw_str)
        out.append(
            {
                "mac": mac,
                "kind": kind,
                "rssi": _int_or_none(row.get("rssi")),
                "major": major,
                "minor": minor,
                "acc": row_acc(row, raw_str),
                "battery": row_battery(row, raw_str),
                "row": row,
            }
        )
    return out


def parse_hub_ids(topic: str) -> tuple[str | None, str | None]:
    """Extract home_id / hub_id from LiveWell or Minew topic shapes."""
    parts = [p for p in (topic or "").split("/") if p != ""]
    if len(parts) >= 5 and parts[0] == "livewell":
        return parts[2], parts[4]
    # /mg7/{mac}/status or mg7/{mac}/status
    if len(parts) >= 2 and parts[0].lower() == "mg7":
        return None, parts[1]
    return None, None


def topic_filters_from_env(raw: str | None) -> list[str]:
    """Comma-separated MQTT subscribe filters (strip empties)."""
    text = (raw or "").strip()
    if not text:
        return [
            "livewell/homes/+/hubs/+/ble",
            "mg7/+/status",
            "/mg7/+/status",
        ]
    return [t.strip() for t in text.split(",") if t.strip()]
