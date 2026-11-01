import pytest

from app.services.readiness_service import _band


@pytest.mark.parametrize(
    "score,expected",
    [
        (100, "GOLD"),
        (90, "GOLD"),
        (89.9, "SILVER"),
        (75, "SILVER"),
        (74.9, "BRONZE"),
        (60, "BRONZE"),
        (59.9, "NOT_READY"),
        (0, "NOT_READY"),
        (-1, "NOT_READY"),
    ],
)
def test_readiness_band(score, expected):
    assert _band(score) == expected
