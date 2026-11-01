"""Address geocoding via OpenStreetMap Nominatim (no API key required)."""

import logging

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "WorkforceOS/1.0 (care coordination platform)"


def geocode_address(address: str) -> tuple[float, float] | None:
    """Return (latitude, longitude) for a free-text address, or None if not found."""
    query = (address or "").strip()
    if len(query) < 3:
        return None

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(
                NOMINATIM_URL,
                params={"q": query, "format": "json", "limit": 1},
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            results = response.json()
            if not results:
                return None
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as exc:
        logger.warning("Geocoding failed for %r: %s", query, exc)
        return None


def apply_coords_to_attributes(
    attributes: dict | None,
    address: str | None,
    *,
    previous_address: str | None = None,
) -> dict | None:
    """Set or clear latitude/longitude in custom_attributes from address."""
    attrs = dict(attributes or {})
    normalized = (address or "").strip()
    prev = (previous_address or "").strip()

    if not normalized:
        attrs.pop("latitude", None)
        attrs.pop("longitude", None)
        return attrs or None

    if prev and normalized == prev and attrs.get("latitude") is not None and attrs.get("longitude") is not None:
        return attrs or None

    coords = geocode_address(normalized)
    if coords:
        attrs["latitude"], attrs["longitude"] = coords
    elif prev and normalized != prev:
        attrs.pop("latitude", None)
        attrs.pop("longitude", None)

    return attrs or None
