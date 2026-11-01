from app.core.geofence_utils import (
    DEFAULT_RADIUS_METERS,
    MIN_GPS_ACCURACY_METERS,
    haversine_meters,
    max_gps_accuracy_meters,
    within_geofence,
)


def test_haversine_zero_and_positive():
    assert haversine_meters(17.4, 78.4, 17.4, 78.4) == 0
    assert haversine_meters(17.4, 78.4, 17.41, 78.41) > 0


def test_within_geofence_same_point():
    inside, distance = within_geofence(17.4, 78.4, 17.4, 78.4, DEFAULT_RADIUS_METERS)
    assert inside is True
    assert distance == 0


def test_gps_accuracy_setting_is_positive():
    assert max_gps_accuracy_meters() > 0
    assert MIN_GPS_ACCURACY_METERS == max_gps_accuracy_meters()
