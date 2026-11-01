"""Geofence distance helpers — core math plus app GPS accuracy setting."""

from app.core.config import settings
from workforceos_core.geo import (
    DEFAULT_RADIUS_METERS,
    EARTH_RADIUS_M,
    haversine_meters,
    within_geofence,
)


def max_gps_accuracy_meters() -> float:
    return float(settings.MAX_GPS_ACCURACY_METERS)


MIN_GPS_ACCURACY_METERS = max_gps_accuracy_meters()

__all__ = [
    "DEFAULT_RADIUS_METERS",
    "EARTH_RADIUS_M",
    "MIN_GPS_ACCURACY_METERS",
    "haversine_meters",
    "max_gps_accuracy_meters",
    "within_geofence",
]
