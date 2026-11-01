import pytest

from app.services.attendance_workflow_service import (
    WORKFLOW_ALERT_TYPES,
    normalize_alert_type,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("late", "LATE"),
        ("LATE", "LATE"),
        ("no_show", "NO_SHOW"),
        ("MISSED_ARRIVAL", "MISSED_CHECKIN"),
        ("missed_arrival", "MISSED_CHECKIN"),
        ("DEPARTURE", "GEOFENCE_VIOLATION"),
        ("departure", "GEOFENCE_VIOLATION"),
        ("GEOFENCE_VIOLATION", "GEOFENCE_VIOLATION"),
        ("MISSED_CHECKIN", "MISSED_CHECKIN"),
        (None, ""),
        ("", ""),
        ("custom", "CUSTOM"),
    ],
)
def test_normalize_alert_type(raw, expected):
    assert normalize_alert_type(raw) == expected


def test_workflow_alert_types_include_normalized_values():
    assert "LATE" in WORKFLOW_ALERT_TYPES
    assert "MISSED_CHECKIN" in WORKFLOW_ALERT_TYPES
    assert "GEOFENCE_VIOLATION" in WORKFLOW_ALERT_TYPES
