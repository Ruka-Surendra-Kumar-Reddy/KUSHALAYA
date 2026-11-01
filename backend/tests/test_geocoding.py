from unittest.mock import patch

from app.core.geocoding import apply_coords_to_attributes, geocode_address


def test_geocode_address_parses_nominatim_response():
    mock_response = [{"lat": "34.0781034", "lon": "-84.2829513"}]
    with patch("app.core.geocoding.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value.json.return_value = (
            mock_response
        )
        client_cls.return_value.__enter__.return_value.get.return_value.raise_for_status = (
            lambda: None
        )
        coords = geocode_address("2450 Clairview St, Alpharetta, GA")
    assert coords == (34.0781034, -84.2829513)


def test_apply_coords_to_attributes_sets_lat_lon():
    with patch("app.core.geocoding.geocode_address", return_value=(17.42, 78.47)):
        attrs = apply_coords_to_attributes({}, "45 Banjara Hills, Hyderabad")
    assert attrs == {"latitude": 17.42, "longitude": 78.47}


def test_apply_coords_to_attributes_clears_coords_when_address_removed():
    attrs = apply_coords_to_attributes(
        {"latitude": 17.42, "longitude": 78.47, "language_preference": "Telugu"},
        "",
    )
    assert attrs == {"language_preference": "Telugu"}


def test_apply_coords_to_attributes_keeps_coords_when_address_unchanged():
    existing = {
        "address": "45 Banjara Hills",
        "latitude": 17.42,
        "longitude": 78.47,
    }
    with patch("app.core.geocoding.geocode_address") as geocode:
        attrs = apply_coords_to_attributes(
            existing,
            "45 Banjara Hills",
            previous_address="45 Banjara Hills",
        )
    geocode.assert_not_called()
    assert attrs["latitude"] == 17.42
