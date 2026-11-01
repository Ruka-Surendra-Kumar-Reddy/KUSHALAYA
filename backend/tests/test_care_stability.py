"""Care stability status engine — Mom-is-OK rules."""

from datetime import datetime, timedelta, timezone

from app.livewell.care_stability import (
    STATUS_GREEN,
    STATUS_RED,
    STATUS_UNKNOWN,
    STATUS_YELLOW,
    compute_care_status,
    family_status_report,
    normalize_checkin,
)


def _visit(checkin: dict, *, days_ago: int = 0, status: str = "completed") -> dict:
    when = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "id": f"hsv_test_{days_ago}",
        "status": status,
        "visited_at": when.isoformat(),
        "staff_name": "Priya",
        "summary": "",
        "checkin": checkin,
    }


def test_normalize_checkin_defaults():
    c = normalize_checkin({"overall": "minor_concern", "bogus": 1})
    assert c["overall"] == "minor_concern"
    assert c["mobility"] == "normal_for_them"
    assert c["medication"] == "none"


def test_green_when_normal_recent_checkin():
    status = compute_care_status(
        visits=[
            _visit(
                {
                    "overall": "normal",
                    "mood": "normal",
                    "mobility": "normal_for_them",
                    "eating": "normal",
                    "medication": "none",
                    "contact_outcome": "answered_normal",
                }
            )
        ]
    )
    assert status["level"] == STATUS_GREEN
    report = family_status_report(status, senior_name="Lakshmi Rao")
    assert "OK" in report["headline"] or "is OK" in report["headline"]


def test_red_on_fall():
    status = compute_care_status(
        visits=[_visit({"overall": "normal", "mobility": "fall", "contact_outcome": "answered_normal"})]
    )
    assert status["level"] == STATUS_RED
    assert any("Fall" in r for r in status["reasons"])


def test_red_on_open_incident():
    status = compute_care_status(
        visits=[_visit({"overall": "normal", "mobility": "normal_for_them"})],
        open_incidents=1,
    )
    assert status["level"] == STATUS_RED


def test_yellow_on_medication_refill():
    status = compute_care_status(
        visits=[
            _visit(
                {
                    "overall": "normal",
                    "mobility": "normal_for_them",
                    "medication": "refill",
                    "contact_outcome": "answered_normal",
                }
            )
        ]
    )
    assert status["level"] == STATUS_YELLOW


def test_yellow_on_two_mobility_declines():
    status = compute_care_status(
        visits=[
            _visit(
                {"overall": "normal", "mobility": "slight_decline", "mobility_vs_normal": "slightly_worse"},
                days_ago=0,
            ),
            _visit(
                {"overall": "normal", "mobility": "slight_decline", "mobility_vs_normal": "slightly_worse"},
                days_ago=3,
            ),
        ]
    )
    assert status["level"] == STATUS_YELLOW
    assert any("multiple" in r.lower() for r in status["reasons"])


def test_unknown_without_checkin():
    status = compute_care_status(visits=[{"status": "completed", "visited_at": datetime.now(timezone.utc).isoformat()}])
    assert status["level"] == STATUS_UNKNOWN


def test_baseline_helpers():
    from app.livewell.care_stability import (
        baseline_minimum_ok,
        is_baseline_established,
        normalize_baseline,
    )

    assert not is_baseline_established(None)
    assert not baseline_minimum_ok({})
    assert baseline_minimum_ok({"typical_mobility": "Walker"})
    assert baseline_minimum_ok({"mobility_band": "walker"})
    established = normalize_baseline({"typical_mobility": "Walker", "updated_at": datetime.now(timezone.utc).isoformat()})
    assert is_baseline_established(established)
    assert established["baseline_stability_score"] == 50


def test_stability_score_baseline_is_50():
    from app.livewell.care_stability import compute_stability_score

    result = compute_stability_score(None, is_baseline_visit=True)
    assert result["score"] == 50
    assert result["delta_from_baseline"] == 0
    assert result["band"] == "baseline"


def test_stability_score_can_improve_above_50():
    from app.livewell.care_stability import compute_stability_score

    result = compute_stability_score(
        {
            "overall": "normal",
            "mood": "normal",
            "mobility": "normal_for_them",
            "eating": "normal",
            "medication": "none",
            "contact_outcome": "answered_normal",
            "mobility_vs_normal": "better",
            "mood_vs_normal": "better",
            "eating_vs_normal": "same",
        }
    )
    assert result["score"] is not None
    assert result["score"] > 50
    assert result["delta_from_baseline"] > 0


def test_stability_score_declines_and_fall_is_low():
    from app.livewell.care_stability import compute_stability_score

    worse = compute_stability_score(
        {
            "overall": "minor_concern",
            "mood": "low",
            "mobility": "slight_decline",
            "eating": "reduced",
            "medication": "missed",
            "contact_outcome": "answered_confused",
            "mobility_vs_normal": "slightly_worse",
            "mood_vs_normal": "slightly_worse",
            "eating_vs_normal": "slightly_worse",
            "unsteady": "yes",
        }
    )
    assert worse["score"] is not None
    assert worse["score"] < 50

    fall = compute_stability_score(
        {
            "overall": "normal",
            "mobility": "fall",
            "fallen_since_last": "yes",
            "contact_outcome": "answered_normal",
        }
    )
    assert fall["score"] is not None
    assert fall["score"] <= 25


_NORMAL = {
    "overall": "normal",
    "mood": "normal",
    "mobility": "normal_for_them",
    "eating": "normal",
    "medication": "none",
    "contact_outcome": "answered_normal",
}


def test_stale_contact_counts_recent_care_visit():
    """Family round 2: a care visit 4 days ago is confirmed contact, even when the
    last check-in is older (no "No confirmed contact in 7+ days")."""
    old = [_visit(_NORMAL, days_ago=12)]
    stale = compute_care_status(visits=old)
    assert any("No confirmed contact" in r for r in stale["reasons"])
    recent = datetime.now(timezone.utc) - timedelta(days=4)
    fresh = compute_care_status(visits=old, last_contact_at=recent)
    assert not any("No confirmed contact" in r for r in fresh["reasons"])
    # A newer completed visit without a check-in also counts.
    no_checkin = {"status": "completed", "visited_at": recent.isoformat()}
    assert not any(
        "No confirmed contact" in r for r in compute_care_status(visits=[*old, no_checkin])["reasons"]
    )
