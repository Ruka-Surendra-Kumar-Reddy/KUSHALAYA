from app.core.monitoring_config import DEFAULT_MONITORING_CONFIG, merge_monitoring_config


def test_merge_none_returns_defaults_copy():
    merged = merge_monitoring_config(None)
    assert merged["notify_family"] is True
    assert merged["no_movement_hours"] == 4
    merged["no_movement_hours"] = 99
    assert DEFAULT_MONITORING_CONFIG["no_movement_hours"] == 4


def test_merge_empty_dict():
    assert merge_monitoring_config({})["channels"] == ["email", "sms", "whatsapp"]


def test_merge_overrides_known_keys():
    merged = merge_monitoring_config({"notify_family": False, "no_movement_hours": 8})
    assert merged["notify_family"] is False
    assert merged["no_movement_hours"] == 8
    assert merged["auto_incident_on_fall"] is True


def test_merge_keeps_extra_keys():
    merged = merge_monitoring_config({"pagerduty": True})
    assert merged["pagerduty"] is True


def test_default_zones_include_privacy_areas():
    assert "bathroom" in DEFAULT_MONITORING_CONFIG["restricted_zones"]
    assert "living_room" in DEFAULT_MONITORING_CONFIG["allowed_zones"]
