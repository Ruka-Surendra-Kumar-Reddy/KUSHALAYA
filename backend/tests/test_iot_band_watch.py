"""Band last-seen / last-motion watch: offline vs immobility vs SOS dedupe."""

from datetime import datetime, timezone

from iot_ingestor.band_watch import (
    BandState,
    WatchPolicy,
    evaluate_watch,
    immobility_skip_reason,
    sos_should_post,
    within_active_hours,
)

DAY = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
NIGHT = datetime(2026, 9, 2, 22, 0, tzinfo=timezone.utc)


def test_sos_fires_on_press_not_repeat_ads():
    policy = WatchPolicy(sos_dedupe_seconds=65)
    state = BandState(mac="c3:00:00:98:f3:f8")
    assert sos_should_post(state, 0.0, policy) is True
    assert sos_should_post(state, 1.0, policy) is False
    assert sos_should_post(state, 64.9, policy) is False
    state.sos_latched = False
    assert sos_should_post(state, 10.0, policy) is True
    assert sos_should_post(state, 11.0, policy) is False


def test_offline_when_unseen():
    policy = WatchPolicy(offline_enabled=True, offline_seconds=180, quiet_period_minutes=60)
    state = BandState(mac="aa:bb:cc:dd:ee:ff")
    state.note_seen(1_000.0)
    assert evaluate_watch(state, 1_000.0 + 179, policy, wall_now=DAY) is None
    assert evaluate_watch(state, 1_000.0 + 181, policy, wall_now=DAY) == "DEVICE_OFFLINE"
    assert evaluate_watch(state, 1_000.0 + 182, policy, wall_now=DAY) is None


def test_power_off_is_offline_not_immobility():
    policy = WatchPolicy(
        offline_enabled=True,
        offline_seconds=180,
        immobility_enabled=True,
        immobility_minutes=1,
        quiet_period_minutes=60,
    )
    state = BandState(mac="aa:bb:cc:dd:ee:ff")
    state.note_motion(1_000.0)
    assert evaluate_watch(state, 1_000.0 + 400, policy, wall_now=DAY) == "DEVICE_OFFLINE"


def test_immobility_requires_motion_slot_and_online():
    policy = WatchPolicy(
        offline_enabled=True,
        offline_seconds=180,
        immobility_enabled=True,
        immobility_minutes=30,
        quiet_period_minutes=60,
    )
    state = BandState(mac="aa:bb:cc:dd:ee:ff")
    now = 10_000.0
    state.note_seen(now)
    assert evaluate_watch(state, now, policy, wall_now=DAY) is None

    state.note_motion(now - 31 * 60)
    state.note_seen(now)
    assert evaluate_watch(state, now, policy, wall_now=DAY) == "IMMOBILITY_WARNING"
    assert evaluate_watch(state, now + 1, policy, wall_now=DAY) is None


def test_immobility_skipped_outside_active_hours():
    policy = WatchPolicy(
        immobility_enabled=True,
        immobility_minutes=30,
        offline_seconds=180,
        active_hours_start=7,
        active_hours_end=21,
        timezone="UTC",
    )
    state = BandState(mac="aa:bb:cc:dd:ee:ff")
    now = 10_000.0
    state.note_motion(now - 40 * 60)
    state.note_seen(now)
    assert evaluate_watch(state, now, policy, wall_now=NIGHT) is None
    assert evaluate_watch(state, now, policy, wall_now=DAY) == "IMMOBILITY_WARNING"


def test_immobility_enabled_by_default():
    policy = WatchPolicy.from_dict({})
    assert policy.immobility_enabled is True
    assert policy.timezone == "Asia/Kolkata"


def test_accelerometer_first_sample_starts_stillness_clock():
    state = BandState(mac="c3:00:00:98:f3:f8")
    assert state.note_accelerometer((7, 0, 250), 1_000.0) is False
    assert state.last_motion_at == 1_000.0
    assert state.note_accelerometer((10, 0, 253), 1_001.0) is False
    assert state.last_motion_at == 1_000.0
    assert state.note_accelerometer((-64, -115, 227), 1_002.0) is True
    assert state.last_motion_at == 1_002.0


def test_immobility_after_still_baseline_without_shake():
    """Band left still after first A103 should alert — no large shake required."""
    policy = WatchPolicy(
        offline_enabled=True,
        offline_seconds=180,
        immobility_enabled=True,
        immobility_minutes=15,
        quiet_period_minutes=60,
        timezone="America/New_York",
        active_hours_start=7,
        active_hours_end=21,
    )
    state = BandState(mac="c3:00:00:98:f3:f8")
    t0 = 10_000.0
    state.note_accelerometer((7, 0, 250), t0)
    # Still ads keep the band online; tiny XYZ noise must not reset stillness.
    for i in range(1, 16):
        state.note_accelerometer((7 + (i % 2), 0, 250), t0 + i * 60)
    evening = datetime(2026, 9, 3, 20, 15, tzinfo=timezone.utc)  # 16:15 EDT
    assert state.last_motion_at == t0
    assert evaluate_watch(state, t0 + 14 * 60, policy, wall_now=evening) is None
    assert evaluate_watch(state, t0 + 15 * 60, policy, wall_now=evening) == "IMMOBILITY_WARNING"


def test_within_active_hours_overnight_wrap():
    policy = WatchPolicy(active_hours_start=21, active_hours_end=7, timezone="UTC")
    assert within_active_hours(datetime(2026, 9, 2, 22, tzinfo=timezone.utc), policy) is True
    assert within_active_hours(datetime(2026, 9, 2, 6, tzinfo=timezone.utc), policy) is True
    assert within_active_hours(datetime(2026, 9, 2, 12, tzinfo=timezone.utc), policy) is False


def test_immobility_skip_reason_outside_hours():
    policy = WatchPolicy(
        immobility_enabled=True,
        immobility_minutes=15,
        offline_seconds=180,
        active_hours_start=7,
        active_hours_end=21,
        timezone="America/New_York",
    )
    state = BandState(mac="aa:bb:cc:dd:ee:ff")
    now = 10_000.0
    state.note_accelerometer((7, 0, 250), now - 20 * 60)
    state.note_seen(now)
    late = datetime(2026, 9, 4, 3, 0, tzinfo=timezone.utc)  # 23:00 EDT
    reason = immobility_skip_reason(state, now, policy, wall_now=late)
    assert reason and reason.startswith("outside_active_hours")

