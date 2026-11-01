from app.livewell.iot_broker_settings import (
    TOPIC_MODE_LIVEWELL,
    TOPIC_MODE_MINEW,
    mac_compact,
    publish_topic_for_mac,
)
from app.livewell.iot_registry_service import normalize_mac
from workforceos_core.exceptions import WorkforceHTTPError
import pytest


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("aa:bb:cc:dd:ee:ff", "AABBCCDDEEFF"),
        ("AA-BB-CC-DD-EE-FF", "AABBCCDDEEFF"),
        ("aabbccddeeff", "AABBCCDDEEFF"),
        ("", ""),
        ("zz", ""),
    ],
)
def test_mac_compact(raw, expected):
    assert mac_compact(raw) == expected


def test_publish_topic_minew_valid_and_invalid():
    broker = {"topic_mode": TOPIC_MODE_MINEW}
    assert publish_topic_for_mac(broker, "AA:BB:CC:DD:EE:FF") == "/mg7/AABBCCDDEEFF/status"
    assert publish_topic_for_mac(broker, "bad") == "/mg7/{bandMac}/status"


def test_publish_topic_livewell_mode():
    broker = {"topic_mode": TOPIC_MODE_LIVEWELL}
    assert (
        publish_topic_for_mac(broker, "AA:BB:CC:DD:EE:FF", home_key="h1", hub_key="hub-2")
        == "livewell/homes/h1/hubs/hub-2/ble"
    )


def test_normalize_mac_valid():
    assert normalize_mac("AA-BB-CC-DD-EE-FF") == "aa:bb:cc:dd:ee:ff"


def test_normalize_mac_rejects_short():
    with pytest.raises(WorkforceHTTPError):
        normalize_mac("aabbcc")
