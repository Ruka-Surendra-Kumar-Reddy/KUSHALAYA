"""Unit tests for Minew MG7 / B7 MQTT decode."""

from iot_ingestor.decode import (
    KIND_SEEN,
    KIND_SOS,
    acc_delta_is_motion,
    extract_b7_signals,
    extract_mac_and_sos,
    normalize_mac,
    parse_hub_ids,
    parse_ibeacon_major_minor,
    parse_minew_acc,
    topic_filters_from_env,
)

SOS_RAW = "0201061AFF4C000215FDA50693A4E24FB1AFCFC6EB0764782500010001C5"
IDLE_RAW = "0201061AFF4C000215FDA50693A4E24FB1AFCFC6EB0764782500000000C5"
IBEACON_12_RAW = "0201061AFF4C000215FDA50693A4E24FB1AFCFC6EB0764782500010002C5"
F1FF_12_RAW = "0201060303F1FF1716FDA50693A4E24FB1AFCFC6EB0764782500010002C564"
ACC_REST_RAW = "0201060303E1FF1216E1FFA103640007000000FAF8F3980000C3"
ACC_MOVE_RAW = "0201060303E1FF1216E1FFA10364FFC0FF8D00E3F8F3980000C3"

MINEW_SOS_BATCH = [
    {
        "timestamp": "2026-09-03T03:02:23.307Z",
        "type": "Gateway",
        "mark_name": "gw-poc-1",
        "mac": "3CDC753C23A4",
        "nums": 5,
    },
    {
        "timestamp": "2026-09-03T03:02:23.321Z",
        "mac": "C3000098F3F8",
        "rssi": -42,
        "rawData": SOS_RAW,
    },
]

MINEW_IDLE_BATCH = [
    {"type": "Gateway", "mac": "3CDC753C23A4", "nums": 1},
    {"mac": "C3000098F3F8", "rssi": -50, "rawData": IDLE_RAW},
]


def test_normalize_mac_compact():
    assert normalize_mac("C3000098F3F8") == "c3:00:00:98:f3:f8"


def test_parse_ibeacon_sos_major_minor():
    assert parse_ibeacon_major_minor(SOS_RAW) == (1, 1)
    assert parse_ibeacon_major_minor(IDLE_RAW) == (0, 0)
    assert parse_ibeacon_major_minor(IBEACON_12_RAW) == (1, 2)
    assert parse_ibeacon_major_minor(F1FF_12_RAW) == (1, 2)


def test_parse_minew_acc_rest_and_move():
    assert parse_minew_acc(ACC_REST_RAW) == (7, 0, 250)
    assert parse_minew_acc(ACC_MOVE_RAW) == (-64, -115, 227)
    assert acc_delta_is_motion(None, (7, 0, 250)) is False
    assert acc_delta_is_motion((7, 0, 250), (10, 0, 253)) is False
    assert acc_delta_is_motion((7, 0, 250), (-64, -115, 227)) is True


def test_extract_b7_signals_sos_ibeacon12_seen_acc():
    sos = extract_b7_signals(MINEW_SOS_BATCH)
    assert len(sos) == 1
    assert sos[0]["mac"] == "c3:00:00:98:f3:f8"
    assert sos[0]["kind"] == KIND_SOS
    assert sos[0]["major"] == 1 and sos[0]["minor"] == 1

    idle = extract_b7_signals(MINEW_IDLE_BATCH)
    assert idle[0]["kind"] == KIND_SEEN
    assert idle[0]["major"] == 0 and idle[0]["minor"] == 0

    slot12 = extract_b7_signals(
        [
            {"type": "Gateway", "mac": "3CDC753C23A4"},
            {"mac": "C3000098F3F8", "rssi": -44, "rawData": IBEACON_12_RAW},
        ]
    )
    assert slot12[0]["kind"] == KIND_SEEN
    assert slot12[0]["major"] == 1 and slot12[0]["minor"] == 2

    acc = extract_b7_signals(
        [
            {"type": "Gateway", "mac": "3CDC753C23A4"},
            {"mac": "C3000098F3F8", "rssi": -46, "rawData": ACC_MOVE_RAW},
        ]
    )
    assert acc[0]["kind"] == KIND_SEEN
    assert acc[0]["acc"] == (-64, -115, 227)


def test_extract_minew_batch_sos():
    mac, sos, raw = extract_mac_and_sos(MINEW_SOS_BATCH)
    assert sos is True
    assert mac == "c3:00:00:98:f3:f8"
    assert raw.get("rssi") == -42
    assert raw.get("major_minor") == (1, 1)


def test_extract_minew_batch_idle_not_sos():
    mac, sos, _ = extract_mac_and_sos(MINEW_IDLE_BATCH)
    assert sos is False
    assert mac == "c3:00:00:98:f3:f8"


def test_extract_lab_sos_dict():
    mac, sos, _ = extract_mac_and_sos({"mac": "AA:BB:CC:DD:EE:FF", "sos": True})
    assert sos is True
    assert mac == "aa:bb:cc:dd:ee:ff"


def test_parse_hub_ids_minew_leading_slash():
    home, hub = parse_hub_ids("/mg7/C3000098F3F8/status")
    assert home is None
    assert hub == "C3000098F3F8"


def test_parse_hub_ids_livewell():
    home, hub = parse_hub_ids("livewell/homes/home1/hubs/mg7-1/ble")
    assert home == "home1"
    assert hub == "mg7-1"


def test_topic_filters_default_includes_mg7():
    filters = topic_filters_from_env(None)
    assert "livewell/homes/+/hubs/+/ble" in filters
    assert "/mg7/+/status" in filters
    assert "mg7/+/status" in filters
