from types import SimpleNamespace

import pytest

from app.services.workforce_service import (
    BENCH_CATEGORIES,
    _bench_category,
    _city_from_attrs,
    _languages_from_attrs,
    _month_start,
)
from datetime import date


@pytest.mark.parametrize(
    "attrs,expected",
    [
        (None, None),
        ({}, None),
        ({"address": ""}, None),
        ({"address": 12}, None),
        ({"city": "Hyderabad"}, "Hyderabad"),
        ({"address": "Banjara Hills, Hyderabad"}, "Hyderabad"),
        ({"address": "Jubilee Hills"}, "Jubilee Hills"),
        ({"address": "A, B, Secunderabad"}, "Secunderabad"),
    ],
)
def test_city_from_attrs(attrs, expected):
    assert _city_from_attrs(attrs) == expected


@pytest.mark.parametrize(
    "attrs,expected",
    [
        (None, []),
        ({}, []),
        ({"languages": "English"}, []),
        ({"languages": ["English", "Hindi", ""]}, ["English", "Hindi"]),
        ({"languages": list("abcdefghijk")}, list("abcdefghij")),
    ],
)
def test_languages_from_attrs(attrs, expected):
    assert _languages_from_attrs(attrs) == expected


def test_month_start_workforce():
    assert _month_start(date(2026, 1, 31)) == date(2026, 1, 1)


def _cg(**kwargs):
    return SimpleNamespace(
        custom_attributes=kwargs.get("custom_attributes") or {},
        background_check_status=kwargs.get("background_check_status"),
    )


def test_bench_category_restricted_flags():
    readiness = {"readiness_score": 99, "breakdown": {"verification": 20}}
    assert _bench_category(_cg(custom_attributes={"restricted": True}), readiness) == "RESTRICTED"
    assert (
        _bench_category(_cg(background_check_status="FAILED"), readiness) == "RESTRICTED"
    )


@pytest.mark.parametrize(
    "score,verification,expected",
    [
        (90, 20, "READY"),
        (75, 20, "AWAITING_PLACEMENT"),
        (70, 10, "VERIFICATION"),
        (70, 15, "TRAINING"),
        (50, 20, "TRAINING"),
    ],
)
def test_bench_category_score_bands(score, verification, expected):
    readiness = {"readiness_score": score, "breakdown": {"verification": verification}}
    assert _bench_category(_cg(), readiness) == expected


def test_bench_categories_tuple():
    assert "READY" in BENCH_CATEGORIES
    assert "TRAINING" in BENCH_CATEGORIES
