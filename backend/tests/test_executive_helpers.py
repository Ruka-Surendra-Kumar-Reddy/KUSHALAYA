from types import SimpleNamespace

import pytest

from app.services.executive_service import (
    DEFAULT_BENCH_COST_PER_CAREGIVER_MONTH_INR,
    _inr_lakhs,
    _month_start,
    _recommended_action,
    bench_cost_per_caregiver_month,
)
from datetime import date


@pytest.mark.parametrize(
    "amount,expected",
    [
        (0, 0.0),
        (100_000, 1.0),
        (150_000, 1.5),
        (1_234_567, 12.35),
        (50_000, 0.5),
    ],
)
def test_inr_lakhs(amount, expected):
    assert _inr_lakhs(amount) == expected


def test_month_start():
    assert _month_start(date(2026, 9, 16)) == date(2026, 9, 1)


@pytest.mark.parametrize(
    "code",
    [
        "HIGH_BENCH",
        "ELDERS_WITHOUT_CAREGIVER",
        "PLACEMENT_OPPORTUNITY",
        "OVERDUE_RECRUITMENT_FOLLOW_UPS",
        "PENDING_DOCUMENTS",
        "PLACEMENT_VELOCITY_DOWN",
        "CRITICAL_INCIDENT",
        "OPEN_INCIDENTS",
        "CERTIFICATION_EXPIRING",
        "NO_SHOW_RISK",
        "UNKNOWN_CODE",
    ],
)
def test_recommended_action_never_empty(code):
    assert _recommended_action(code)


def test_recommended_action_fallback():
    assert "Command Center" in _recommended_action("NOT_A_REAL_CODE")


def test_bench_cost_default_when_tenant_missing():
    class _Db:
        def query(self, model):
            class Q:
                def filter(self, *a, **k):
                    return self

                def first(self):
                    return None

            return Q()

    assert bench_cost_per_caregiver_month(_Db(), 1) == DEFAULT_BENCH_COST_PER_CAREGIVER_MONTH_INR


def test_bench_cost_uses_tenant_override():
    class _Db:
        def query(self, model):
            class Q:
                def filter(self, *a, **k):
                    return self

                def first(self):
                    return SimpleNamespace(bench_cost_per_caregiver_month_inr=22000)

            return Q()

    assert bench_cost_per_caregiver_month(_Db(), 9) == 22000.0
