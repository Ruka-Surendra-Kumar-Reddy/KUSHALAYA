"""Unit tests for Wearables MQTT broker settings (source of truth)."""

from app.livewell.iot_broker_settings import (
    TOPIC_MODE_LIVEWELL,
    TOPIC_MODE_MINEW,
    _normalize,
    ingest_watch_policy,
    publish_topic_for_mac,
)


def test_publish_topic_minew_status():
    broker = _normalize({"topic_mode": TOPIC_MODE_MINEW})
    assert publish_topic_for_mac(broker, "c3:00:00:98:f3:f8") == "/mg7/C3000098F3F8/status"


def test_publish_topic_livewell_ble():
    broker = _normalize({"topic_mode": TOPIC_MODE_LIVEWELL})
    assert (
        publish_topic_for_mac(broker, "aa:bb:cc:dd:ee:ff", home_key="home1", hub_key="mg7-1")
        == "livewell/homes/home1/hubs/mg7-1/ble"
    )


def test_normalize_defaults_shared_hub():
    data = _normalize({})
    assert data["use_shared_hub"] is True
    assert data["topic_mode"] == TOPIC_MODE_MINEW
    assert data["subscribe_topic"] == ""
    assert data["reply_topic"] == ""
    assert data["ingestor_username"] == "livewell_ingestor"
    assert "mg7/+/status" in data["ingestor_mqtt_topic"]
    assert "/mg7/+/status" in data["ingestor_mqtt_topic"]
    assert data["dedupe_seconds"] == 65
    assert data["immobility_enabled"] is True
    assert data["timezone"] == "Asia/Kolkata"
    assert data["watch_policy_version"] == 2
    assert data["offline_enabled"] is True
    assert data["offline_seconds"] == 180
    assert data["immobility_minutes"] == 30
    assert data["quiet_period_minutes"] == 60
    assert data["active_hours_start"] == 7
    assert data["active_hours_end"] == 21


def test_normalize_dedupe_clamped():
    assert _normalize({"dedupe_seconds": 0})["dedupe_seconds"] == 1
    assert _normalize({"dedupe_seconds": 99999})["dedupe_seconds"] == 3600
    assert _normalize({"dedupe_seconds": "120"})["dedupe_seconds"] == 120


def test_ingest_watch_policy_maps_sos_dedupe():
    policy = ingest_watch_policy(
        {
            "dedupe_seconds": 65,
            "immobility_enabled": True,
            "immobility_minutes": 30,
            "offline_enabled": True,
            "offline_seconds": 180,
            "quiet_period_minutes": 60,
            "active_hours_start": 7,
            "active_hours_end": 21,
            "timezone": "Asia/Kolkata",
        }
    )
    assert policy["sos_dedupe_seconds"] == 65
    assert policy["immobility_enabled"] is True
    assert policy["timezone"] == "Asia/Kolkata"


def test_watch_policy_v1_enables_immobility_and_kolkata():
    data = _normalize(
        {"immobility_enabled": False, "timezone": "UTC", "immobility_minutes": 5}
    )
    assert data["immobility_enabled"] is True
    assert data["timezone"] == "Asia/Kolkata"
    assert data["watch_policy_version"] == 2
    assert data["immobility_minutes"] == 5


def test_ingest_watch_policy_keeps_custom_immobility_minutes():
    policy = ingest_watch_policy(
        {
            "watch_policy_version": 2,
            "immobility_enabled": True,
            "immobility_minutes": 2,
            "timezone": "Asia/Kolkata",
        }
    )
    assert policy["immobility_minutes"] == 2


def test_watch_policy_v2_keeps_explicit_off():
    data = _normalize(
        {
            "watch_policy_version": 2,
            "immobility_enabled": False,
            "timezone": "UTC",
        }
    )
    assert data["immobility_enabled"] is False
    assert data["timezone"] == "UTC"
