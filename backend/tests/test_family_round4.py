"""Round-4 family fixes: one status, real visit times, caregiver name fallback, IST digest."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.livewell.care_jobs import family_visit_times
from app.livewell.family_care_hub import _zone_words
from app.livewell.family_status import build_family_status


def _job(checked_in=None, completed=None, started=None):
    return SimpleNamespace(checked_in_at=checked_in, started_at=started, completed_at=completed, duration_minutes=60)


def test_same_minute_finish_is_hidden_and_planned_length_never_shown():
    t = datetime(2026, 10, 7, 4, 30, tzinfo=timezone.utc)
    out = family_visit_times(_job(checked_in=t, completed=t + timedelta(seconds=20)))
    assert out["checked_out_at"] is None
    assert out["duration_minutes"] is None  # not the planned 60


def test_real_duration_is_the_time_between_check_in_and_finish():
    t = datetime(2026, 10, 7, 4, 30, tzinfo=timezone.utc)
    out = family_visit_times(_job(checked_in=t, completed=t + timedelta(minutes=47)))
    assert out["checked_out_at"] == t + timedelta(minutes=47)
    assert out["duration_minutes"] == 47


def test_status_lists_noted_changes_beside_the_checks():
    s = build_family_status(
        word="Small changes noted",
        level="ok",
        checks={"safe": "ok", "steady": "ok", "settled": "ok", "connected": "ok"},
        changes=["Slept poorly", "Ate less"],
        last_visit_at=None,
        mobility_sheet="Assisted",
        mobility_checkin="normal_for_them",
    )
    assert s["checks_text"] == "4/4 checks OK · slept poorly, ate less"
    assert s["changes_text"] == "Noted: Slept poorly, Ate less"
    assert s["tone"] == "ok"
    # The care sheet wins over a check-in's "normal for them".
    assert s["mobility"] == "Assisted"


def test_status_tone_and_mobility_fallback():
    s = build_family_status(
        word="Watching closely", level=None, checks=None, changes=[], last_visit_at=None,
        mobility_sheet="", mobility_checkin="normal_for_them",
    )
    assert s["tone"] == "watch"
    assert s["checks_text"] == ""
    assert s["changes_text"] == "No changes noticed"
    assert s["mobility"] == "normal for them"
    assert build_family_status(
        word="We're calling you", level=None, checks=None, changes=[], last_visit_at=None,
        mobility_sheet=None, mobility_checkin=None,
    )["tone"] == "alert"


def test_digest_times_say_ist():
    assert _zone_words("Asia/Kolkata") == "IST"
    assert _zone_words("") == "IST"
    assert _zone_words("Europe/London") == "London time"
