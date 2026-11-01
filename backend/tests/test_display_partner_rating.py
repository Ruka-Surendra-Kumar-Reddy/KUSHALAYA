import pytest

from app.livewell.partner_rating_service import (
    MIN_PUBLIC_COUNT,
    display_partner_rating,
)


@pytest.mark.parametrize(
    "supplier,expected",
    [
        ({}, None),
        ({"rating": 4.5}, 4.5),
        ({"rolling_rating": 4.8, "rolling_rating_count": 1}, 4.8),
        ({"rolling_rating": 4.2, "rolling_rating_count": 3}, 4.2),
        ({"rolling_rating": 4.2, "rolling_rating_count": 5, "rating": 3.0}, 4.2),
        ({"rolling_rating": None, "rolling_rating_count": 5, "rating": 3.1}, 3.1),
        ({"rolling_rating": 4.9, "rolling_rating_count": 0, "rating": 2}, 2.0),
        ({"rolling_rating_count": 2, "rating": "4"}, 4.0),
    ],
)
def test_display_partner_rating(supplier, expected):
    result = display_partner_rating(supplier)
    if expected is None:
        assert result is None
    else:
        assert result == pytest.approx(expected)


def test_min_public_count_threshold():
    assert MIN_PUBLIC_COUNT == 3
    assert display_partner_rating({"rolling_rating": 5, "rolling_rating_count": 2}) == 5.0
