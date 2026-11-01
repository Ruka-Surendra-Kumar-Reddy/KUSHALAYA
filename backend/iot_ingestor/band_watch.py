"""Per-band last-seen / last-motion timers and immobility vs offline rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from iot_ingestor.decode import acc_delta_is_motion


@dataclass
class WatchPolicy:
    sos_dedupe_seconds: float = 65.0
    immobility_enabled: bool = True
    immobility_minutes: float = 30.0
    offline_enabled: bool = True
    offline_seconds: float = 180.0
    quiet_period_minutes: float = 60.0
    active_hours_start: int = 7
    active_hours_end: int = 21
    timezone: str = "Asia/Kolkata"

    @classmethod
    def from_dict(cls, raw: dict | None) -> WatchPolicy:
        d = raw if isinstance(raw, dict) else {}
        p = cls()
        if d.get("sos_dedupe_seconds") is not None or d.get("dedupe_seconds") is not None:
            try:
                p.sos_dedupe_seconds = float(d.get("sos_dedupe_seconds") or d.get("dedupe_seconds") or 65)
            except (TypeError, ValueError):
                pass
        p.immobility_enabled = bool(d.get("immobility_enabled", True))
        for key, attr, default in (
            ("immobility_minutes", "immobility_minutes", 30.0),
            ("offline_seconds", "offline_seconds", 180.0),
            ("quiet_period_minutes", "quiet_period_minutes", 60.0),
        ):
            if d.get(key) is not None:
                try:
                    setattr(p, attr, float(d[key]))
                except (TypeError, ValueError):
                    setattr(p, attr, default)
        p.offline_enabled = bool(d.get("offline_enabled", True))
        try:
            p.active_hours_start = int(d.get("active_hours_start", 7))
            p.active_hours_end = int(d.get("active_hours_end", 21))
        except (TypeError, ValueError):
            p.active_hours_start, p.active_hours_end = 7, 21
        p.timezone = str(d.get("timezone") or "Asia/Kolkata").strip() or "Asia/Kolkata"
        p.sos_dedupe_seconds = max(1.0, min(3600.0, p.sos_dedupe_seconds))
        p.immobility_minutes = max(1.0, min(24 * 60.0, p.immobility_minutes))
        p.offline_seconds = max(30.0, min(3600.0, p.offline_seconds))
        p.quiet_period_minutes = max(1.0, min(24 * 60.0, p.quiet_period_minutes))
        p.active_hours_start = max(0, min(23, p.active_hours_start))
        p.active_hours_end = max(0, min(23, p.active_hours_end))
        return p


def within_active_hours(now: datetime, policy: WatchPolicy) -> bool:
    start, end = policy.active_hours_start, policy.active_hours_end
    if start == end:
        return True
    try:
        tz = ZoneInfo(policy.timezone)
    except Exception:  # noqa: BLE001
        tz = timezone.utc
    hour = now.astimezone(tz).hour
    # Inclusive end hour (07–21 means through 21:59 local).
    if start < end:
        return start <= hour <= end
    return hour >= start or hour <= end


def seconds_into_active_window(now: datetime, policy: WatchPolicy) -> float:
    """Seconds since today's active window opened (call only inside the window).

    Stillness is only counted from the window start, so a client who slept
    through the night is not flagged at 07:00 — only if there is no movement for
    the full threshold after the window opens.
    """
    if policy.active_hours_start == policy.active_hours_end:
        return float("inf")
    try:
        tz = ZoneInfo(policy.timezone)
    except Exception:  # noqa: BLE001
        tz = timezone.utc
    local = now.astimezone(tz)
    start = local.replace(hour=policy.active_hours_start, minute=0, second=0, microsecond=0)
    if start > local:
        start -= timedelta(days=1)
    return (local - start).total_seconds()


def active_hours_label(policy: WatchPolicy, wall_now: datetime) -> str:
    try:
        tz = ZoneInfo(policy.timezone)
        local = wall_now.astimezone(tz)
        local_s = local.strftime("%Y-%m-%d %H:%M %Z")
    except Exception:  # noqa: BLE001
        local_s = wall_now.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"tz={policy.timezone} local={local_s} "
        f"window={policy.active_hours_start:02d}-{policy.active_hours_end:02d}"
    )


@dataclass
class BandState:
    mac: str
    first_seen_at: float | None = None
    last_seen_at: float | None = None
    last_motion_at: float | None = None
    last_acc: tuple[int, int, int] | None = None
    last_sos_at: float | None = None
    sos_latched: bool = False
    last_immobility_alert_at: float | None = None
    last_offline_alert_at: float | None = None
    hub_id: str | None = None

    def note_seen(
        self, now: float, *, hub_id: str | None = None, offline_seconds: float | None = None
    ) -> None:
        """Heard an advertisement. Coming back after an offline gap (out of range,
        flat battery, gateway down) starts a fresh episode: the stillness clock
        restarts from the next accelerometer sample instead of counting the time
        we could not hear the band as "not moving"."""
        if (
            offline_seconds is not None
            and self.last_seen_at is not None
            and now - self.last_seen_at > offline_seconds
        ):
            self.last_motion_at = None
            self.last_acc = None
            self.sos_latched = False
            self.last_immobility_alert_at = None
        if self.first_seen_at is None:
            self.first_seen_at = now
        self.last_seen_at = now
        # Heard again: the next offline episode may alert again.
        self.last_offline_alert_at = None
        if hub_id:
            self.hub_id = hub_id

    def note_motion(self, now: float) -> None:
        self.note_seen(now)
        self.last_motion_at = now
        self.last_immobility_alert_at = None  # moved: re-arm immobility

    def note_accelerometer(self, xyz: tuple[int, int, int], now: float) -> bool:
        """Update last-seen; set last-motion on first A103 sample or a large XYZ change.

        The first sample starts the stillness clock (so a band left still after
        power-on / reconnect can still raise IMMOBILITY_WARNING). Later samples
        only reset the clock when XYZ moves enough.
        """
        first = self.last_acc is None
        moved = acc_delta_is_motion(self.last_acc, xyz)
        self.last_acc = xyz
        self.note_seen(now)
        if first or moved:
            self.last_motion_at = now
            if moved:
                self.last_immobility_alert_at = None  # moved: re-arm immobility
            return moved  # True only for a real move (not the baseline sample)
        return False


def sos_should_post(state: BandState, now: float, policy: WatchPolicy) -> bool:
    """True on the start of an SOS session (button press), not on repeat 1/1 ads.

    Minew B7 keeps advertising major/minor 1/1 for ~60s after a press. Time-only
    dedupe blocked a later single click. Latch until idle (non-SOS) ads return.
    """
    if state.sos_latched:
        return False
    last = state.last_sos_at
    # Tiny gap only — stops MQTT flicker, not a new press after the band goes idle.
    gap = 2.0
    if last is not None and (now - last) < gap:
        return False
    state.sos_latched = True
    state.last_sos_at = now
    return True


def evaluate_watch(state: BandState, now: float, policy: WatchPolicy, *, wall_now: datetime) -> str | None:
    """Return DEVICE_OFFLINE | IMMOBILITY_WARNING | None.

    * Offline (not heard for ``offline_seconds``) is never immobility. One alert
      per offline episode, only in active hours (a band charging overnight away
      from the gateway does not wake anyone; it alerts at the window start).
    * Immobility: heard, but the accelerometer has not moved for
      ``immobility_minutes`` of active hours. One alert per still episode; any
      real movement re-arms it.
    """
    if state.last_seen_at is None:
        return None

    unseen = now - state.last_seen_at
    online = unseen <= policy.offline_seconds
    if not online:
        if (
            policy.offline_enabled
            and state.last_offline_alert_at is None
            and within_active_hours(wall_now, policy)
        ):
            state.last_offline_alert_at = now
            return "DEVICE_OFFLINE"
        return None

    if not policy.immobility_enabled:
        return None
    if not within_active_hours(wall_now, policy):
        return None
    # Stillness clock starts on first A103 sample (or a later XYZ delta).
    # Without any A103 ads, last_motion_at stays None and immobility cannot fire.
    if state.last_motion_at is None:
        return None
    if state.last_immobility_alert_at is not None and state.last_immobility_alert_at >= state.last_motion_at:
        return None  # already alerted for this still episode
    still_for = min(now - state.last_motion_at, seconds_into_active_window(wall_now, policy))
    if still_for < policy.immobility_minutes * 60.0:
        return None
    state.last_immobility_alert_at = now
    return "IMMOBILITY_WARNING"


def immobility_skip_reason(
    state: BandState, now: float, policy: WatchPolicy, *, wall_now: datetime
) -> str | None:
    """Explain why IMMOBILITY_WARNING did not fire (for operator logs)."""
    if state.last_seen_at is None:
        return "never_seen"
    if (now - state.last_seen_at) > policy.offline_seconds:
        return "offline"
    if not policy.immobility_enabled:
        return "immobility_disabled"
    if not within_active_hours(wall_now, policy):
        return f"outside_active_hours ({active_hours_label(policy, wall_now)})"
    if state.last_motion_at is None:
        return "no_a103_baseline_yet (need Minew FFE1 A103 ads)"
    if state.last_immobility_alert_at is not None and state.last_immobility_alert_at >= state.last_motion_at:
        return "already_alerted (waiting for movement)"
    still_for = min(now - state.last_motion_at, seconds_into_active_window(wall_now, policy))
    need = policy.immobility_minutes * 60.0
    if still_for < need:
        return f"still_for={int(still_for)}s need={int(need)}s"
    return None


def policy_public(policy: WatchPolicy) -> dict[str, Any]:
    return {
        "sos_dedupe_seconds": int(policy.sos_dedupe_seconds),
        "dedupe_seconds": int(policy.sos_dedupe_seconds),
        "immobility_enabled": policy.immobility_enabled,
        "immobility_minutes": int(policy.immobility_minutes),
        "offline_enabled": policy.offline_enabled,
        "offline_seconds": int(policy.offline_seconds),
        "quiet_period_minutes": int(policy.quiet_period_minutes),
        "active_hours_start": policy.active_hours_start,
        "active_hours_end": policy.active_hours_end,
        "timezone": policy.timezone,
    }
