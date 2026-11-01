"""Care status must not report "awaiting baseline" when a baseline / check-in exists."""

from datetime import datetime, timedelta, timezone

from app.livewell.care_stability import (
    STATUS_GREEN,
    STATUS_UNKNOWN,
    STATUS_YELLOW,
    compute_care_status,
)


def _visit(checkin, *, days_ago, status="completed", visit_type="Wellness visit"):
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "id": f"hsv_{days_ago}",
        "status": status,
        "visit_type": visit_type,
        "visited_at": when.isoformat(),
        "staff_name": "Priya",
        "checkin": checkin,
    }


NORMAL = {
    "overall": "normal",
    "mood": "normal",
    "mobility": "normal_for_them",
    "eating": "normal",
    "medication": "none",
    "contact_outcome": "answered_normal",
}

BASELINE = {
    "typical_mobility": "Independent with cane",
    "usual_wake_time": "6:30 AM",
    "notes": "Baseline from first visit",
    "updated_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
}


def test_newest_visit_without_checkin_falls_back_to_last_checkin():
    """The demo: an installation visit (no check-in) landed after the wellness
    check-in and the page said "awaiting baseline" next to the stored baseline."""
    status = compute_care_status(
        visits=[
            _visit(None, days_ago=1, visit_type="Installation"),
            _visit({**NORMAL, "medication": "refill"}, days_ago=3),
        ],
        baseline=BASELINE,
    )
    assert status["level"] == STATUS_YELLOW
    assert any("Medication" in r for r in status["reasons"])
    assert status["confirmed_at"] is not None
    assert "hsv_3" not in status["reasons"]


def test_newest_visit_without_checkin_green_when_last_checkin_normal():
    status = compute_care_status(
        visits=[
            _visit({}, days_ago=0, visit_type="Delivery"),
            _visit(NORMAL, days_ago=2),
        ],
        baseline=BASELINE,
    )
    assert status["level"] == STATUS_GREEN
    assert status["snapshot"]["mobility"] == "normal_for_them"


def test_baseline_without_any_checkin_is_ok_not_awaiting():
    status = compute_care_status(
        visits=[_visit(None, days_ago=1, visit_type="Installation")],
        baseline=BASELINE,
    )
    assert status["level"] == STATUS_GREEN
    assert status["label"] == "OK"
    assert any("Baseline profile established" in r for r in status["reasons"])
    assert any("no wellness check-in recorded since" in r for r in status["reasons"])
    assert status["confirmed_at"] is not None
    assert "awaiting" not in status["change_summary"].lower()


def test_no_baseline_no_checkin_still_unknown():
    status = compute_care_status(
        visits=[_visit(None, days_ago=1)],
        baseline={},
    )
    assert status["level"] == STATUS_UNKNOWN
    status = compute_care_status(visits=[], baseline=None)
    assert status["level"] == STATUS_UNKNOWN


def test_care_status_for_elder_uses_stored_baseline(db, seed_tenant):
    """Service-level reproduction: baseline stored on the elder, newest visit has no check-in."""
    from sqlalchemy.orm.attributes import flag_modified

    from app.livewell.visit_service import HomeSafetyVisitService

    elder = seed_tenant["elder"]
    attrs = dict(elder.custom_attributes or {})
    attrs["safe_home"] = {
        "care_baseline": BASELINE,
        "visits": [
            _visit(None, days_ago=1, visit_type="Installation"),
        ],
    }
    elder.custom_attributes = attrs
    flag_modified(elder, "custom_attributes")
    db.commit()

    report = HomeSafetyVisitService.care_status_for_elder(db, elder)
    assert report["level"] == STATUS_GREEN
    assert report["baseline"]["typical_mobility"] == "Independent with cane"
    assert "awaiting" not in (report.get("headline") or "").lower()
