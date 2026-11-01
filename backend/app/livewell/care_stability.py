"""Care stability — baseline + check-in + Mom-is-OK status (Hyderabad pilot).

Not a medical diagnosis. Status is care-coordination: GREEN / YELLOW / RED from
structured visit check-ins, open requests, and hard-coded escalation rules.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

CONTACT_OUTCOMES = (
    "answered_normal",
    "answered_confused",
    "answered_distressed",
    "requested_help",
    "no_answer",
)

OVERALL_STATUS = ("normal", "minor_concern", "significant_concern", "emergency")
MOOD = ("normal", "low", "anxious", "confused")
MOBILITY = ("normal_for_them", "slight_decline", "significant_decline", "fall")
EATING = ("normal", "reduced", "not_eating")
MEDICATION = ("none", "missed", "refill", "change", "concern")
VS_NORMAL = ("better", "same", "slightly_worse", "much_worse")
YN = ("none", "yes")

STATUS_GREEN = "ok"
STATUS_YELLOW = "needs_attention"
STATUS_RED = "urgent"
STATUS_UNKNOWN = "unknown"

STATUS_LABELS = {
    STATUS_GREEN: "OK",
    STATUS_YELLOW: "Needs attention",
    STATUS_RED: "Urgent",
    STATUS_UNKNOWN: "Awaiting baseline",
}

STATUS_FAMILY_HEADLINES = {
    STATUS_GREEN: "is OK ✓",
    STATUS_YELLOW: "needs attention",
    STATUS_RED: "— urgent follow-up",
    STATUS_UNKNOWN: "— awaiting baseline visit",
}

# Centered stability index: 50 = personal normal (baseline). Room to rise (better) or fall (worse).
BASELINE_STABILITY_SCORE = 50
STABILITY_MIN = 0
STABILITY_MAX = 100

MOBILITY_BAND = ("independent", "cane", "walker", "assisted", "chairbound")
APPETITE_BAND = ("good", "fair", "poor")
LEAVES_HOME_BAND = ("daily", "few_times_week", "rarely", "never")
FALL_HISTORY_BAND = ("none", "one_past_year", "multiple", "recent")
COMMUNICATION_BAND = ("clear", "some_difficulty", "confused", "hard_to_engage")
WAKE_BAND = ("before_6", "6_to_7", "7_to_8", "after_8", "irregular")
SLEEP_BAND = ("through_night", "wakes_once", "restless", "day_night_reversed")
ACTIVITY_BAND = ("active_home", "limited", "mostly_seated", "mostly_bed")
BATHROOM_BAND = ("independent", "occasional_help", "night_trips", "needs_assistance")
MEDS_BAND = ("self", "family", "caregiver", "irregular")
HOME_HAZARD_BAND = ("none_seen", "minor", "significant", "not_assessed")
YN_SIMPLE = ("yes", "no")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _pick(value: Any, allowed: tuple[str, ...], default: str) -> str:
    v = str(value or "").strip().lower()
    return v if v in allowed else default


def empty_baseline() -> dict:
    return {
        "usual_wake_time": "",
        "wake_band": "",
        "typical_mobility": "",
        "mobility_band": "",
        "normal_appetite": "",
        "appetite_band": "",
        "normal_communication": "",
        "communication_band": "",
        "typical_bathroom_frequency": "",
        "bathroom_band": "",
        "normal_activity_level": "",
        "activity_band": "",
        "usual_sleep_pattern": "",
        "sleep_band": "",
        "leaves_home_how_often": "",
        "leaves_home_band": "",
        "mobility_limitations": "",
        "known_fall_history": "",
        "fall_history_band": "",
        "typical_medication_routine": "",
        "meds_band": "",
        "home_hazard_band": "",
        "unsteady_at_baseline": "",
        "worried_about_falling_baseline": "",
        "notes": "",
        "context_notes": "",
        "home_glance_notes": "",
        "normal_day_confirmed": "",
        "close_notes": "",
        "updated_at": None,
        "source_visit_id": None,
        "baseline_stability_score": BASELINE_STABILITY_SCORE,
    }


def normalize_baseline(raw: dict | None) -> dict:
    base = empty_baseline()
    if not isinstance(raw, dict):
        return base
    text_keys = (
        "usual_wake_time",
        "typical_mobility",
        "normal_appetite",
        "normal_communication",
        "typical_bathroom_frequency",
        "normal_activity_level",
        "usual_sleep_pattern",
        "leaves_home_how_often",
        "mobility_limitations",
        "known_fall_history",
        "typical_medication_routine",
        "notes",
        "context_notes",
        "home_glance_notes",
        "close_notes",
    )
    for key in text_keys:
        if key in raw and raw[key] is not None:
            base[key] = str(raw[key]).strip()[:500]
    mb = str(raw.get("mobility_band") or "").strip().lower()
    base["mobility_band"] = mb if mb in MOBILITY_BAND else ""
    ab = str(raw.get("appetite_band") or "").strip().lower()
    base["appetite_band"] = ab if ab in APPETITE_BAND else ""
    lh = str(raw.get("leaves_home_band") or "").strip().lower()
    base["leaves_home_band"] = lh if lh in LEAVES_HOME_BAND else ""
    fh = str(raw.get("fall_history_band") or "").strip().lower()
    base["fall_history_band"] = fh if fh in FALL_HISTORY_BAND else ""
    cb = str(raw.get("communication_band") or "").strip().lower()
    base["communication_band"] = cb if cb in COMMUNICATION_BAND else ""
    wb = str(raw.get("wake_band") or "").strip().lower()
    base["wake_band"] = wb if wb in WAKE_BAND else ""
    sb = str(raw.get("sleep_band") or "").strip().lower()
    base["sleep_band"] = sb if sb in SLEEP_BAND else ""
    act = str(raw.get("activity_band") or "").strip().lower()
    base["activity_band"] = act if act in ACTIVITY_BAND else ""
    bath = str(raw.get("bathroom_band") or "").strip().lower()
    base["bathroom_band"] = bath if bath in BATHROOM_BAND else ""
    med = str(raw.get("meds_band") or "").strip().lower()
    base["meds_band"] = med if med in MEDS_BAND else ""
    hh = str(raw.get("home_hazard_band") or "").strip().lower()
    base["home_hazard_band"] = hh if hh in HOME_HAZARD_BAND else ""
    uns = str(raw.get("unsteady_at_baseline") or "").strip().lower()
    base["unsteady_at_baseline"] = uns if uns in YN_SIMPLE else ""
    wor = str(raw.get("worried_about_falling_baseline") or "").strip().lower()
    base["worried_about_falling_baseline"] = wor if wor in YN_SIMPLE else ""
    confirmed = str(raw.get("normal_day_confirmed") or "").strip().lower()
    base["normal_day_confirmed"] = confirmed if confirmed in ("yes", "no", "partial") else ""
    # Keep a combined notes field for older readers
    if not base["notes"]:
        parts = [
            p
            for p in (
                base.get("context_notes"),
                base.get("home_glance_notes"),
                base.get("close_notes"),
            )
            if (p or "").strip()
        ]
        if parts:
            base["notes"] = " | ".join(parts)[:500]
    updated = _parse_dt(raw.get("updated_at"))
    base["updated_at"] = updated.isoformat() if updated else None
    src = raw.get("source_visit_id")
    base["source_visit_id"] = str(src).strip() if src else None
    base["baseline_stability_score"] = BASELINE_STABILITY_SCORE
    return base


def baseline_minimum_ok(raw: dict | None) -> bool:
    base = normalize_baseline(raw)
    return bool(
        (base.get("typical_mobility") or "").strip()
        or (base.get("mobility_band") or "").strip()
        or (base.get("notes") or "").strip()
        or (base.get("context_notes") or "").strip()
        or (base.get("usual_wake_time") or "").strip()
    )


def is_baseline_established(raw: dict | None) -> bool:
    """True after a first baseline visit (or explicit baseline save)."""
    base = normalize_baseline(raw)
    if base.get("updated_at"):
        return True
    for key in (
        "typical_mobility",
        "mobility_band",
        "normal_appetite",
        "usual_wake_time",
        "known_fall_history",
        "fall_history_band",
        "notes",
    ):
        if (base.get(key) or "").strip():
            return True
    return False


BASELINE_VISIT_TYPE = "Baseline profile"


def checkin_for_baseline_visit() -> dict:
    """First visit establishes 'their normal' — vs-normal fields are same by definition."""
    c = empty_checkin()
    c["overall"] = "normal"
    c["mood"] = "normal"
    c["mobility"] = "normal_for_them"
    c["eating"] = "normal"
    c["medication"] = "none"
    c["mobility_vs_normal"] = "same"
    c["mood_vs_normal"] = "same"
    c["eating_vs_normal"] = "same"
    c["contact_outcome"] = "answered_normal"
    return c


def empty_checkin() -> dict:
    return {
        "overall": "normal",
        "mood": "normal",
        "mobility": "normal_for_them",
        "eating": "normal",
        "medication": "none",
        "new_symptoms": "none",
        "symptoms_note": "",
        "home_safety_issue": "none",
        "home_safety_note": "",
        "new_request": "none",
        "request_note": "",
        "follow_up_required": False,
        "contact_outcome": "answered_normal",
        "mobility_vs_normal": "same",
        "mood_vs_normal": "same",
        "eating_vs_normal": "same",
        "fallen_since_last": "no",
        "unsteady": "no",
        "worried_about_falling": "no",
        "care_manager_note": "",
        "family_message": "",
    }


YN_NO = ("no", "yes")


def normalize_checkin(raw: dict | None) -> dict | None:
    if not isinstance(raw, dict) or not raw:
        return None
    c = empty_checkin()
    c["overall"] = _pick(raw.get("overall"), OVERALL_STATUS, "normal")
    c["mood"] = _pick(raw.get("mood"), MOOD, "normal")
    c["mobility"] = _pick(raw.get("mobility"), MOBILITY, "normal_for_them")
    c["eating"] = _pick(raw.get("eating"), EATING, "normal")
    c["medication"] = _pick(raw.get("medication"), MEDICATION, "none")
    c["new_symptoms"] = _pick(raw.get("new_symptoms"), YN, "none")
    c["home_safety_issue"] = _pick(raw.get("home_safety_issue"), YN, "none")
    c["new_request"] = _pick(raw.get("new_request"), YN, "none")
    c["contact_outcome"] = _pick(raw.get("contact_outcome"), CONTACT_OUTCOMES, "answered_normal")
    c["mobility_vs_normal"] = _pick(raw.get("mobility_vs_normal"), VS_NORMAL, "same")
    c["mood_vs_normal"] = _pick(raw.get("mood_vs_normal"), VS_NORMAL, "same")
    c["eating_vs_normal"] = _pick(raw.get("eating_vs_normal"), VS_NORMAL, "same")
    c["fallen_since_last"] = _pick(raw.get("fallen_since_last"), YN_NO, "no")
    c["unsteady"] = _pick(raw.get("unsteady"), YN_NO, "no")
    c["worried_about_falling"] = _pick(raw.get("worried_about_falling"), YN_NO, "no")
    c["follow_up_required"] = bool(raw.get("follow_up_required"))
    c["symptoms_note"] = str(raw.get("symptoms_note") or "").strip()[:1000]
    c["home_safety_note"] = str(raw.get("home_safety_note") or "").strip()[:1000]
    c["request_note"] = str(raw.get("request_note") or "").strip()[:1000]
    c["care_manager_note"] = str(raw.get("care_manager_note") or "").strip()[:2000]
    # Explicit family-facing message; fall back to legacy care_manager_note
    family_msg = str(raw.get("family_message") or raw.get("care_manager_note") or "").strip()[:2000]
    c["family_message"] = family_msg
    if family_msg and not c["care_manager_note"]:
        c["care_manager_note"] = family_msg
    return c


def _vs_delta(value: str, *, better: int = 8, slightly: int = -8, much: int = -16) -> tuple[int, str | None]:
    if value == "better":
        return better, "better than usual"
    if value == "slightly_worse":
        return slightly, "slightly worse than usual"
    if value == "much_worse":
        return much, "much worse than usual"
    return 0, None


def compute_stability_score(
    checkin: dict | None,
    *,
    is_baseline_visit: bool = False,
) -> dict:
    """Centered 0–100 index: 50 = personal normal. Higher = improved vs baseline; lower = declined.

    Care coordination only — not a medical diagnosis. Derived from structured multiple-choice
    check-in fields (aligned with WHO ICOPE domains + CDC STEADI fall cues).
    """
    if is_baseline_visit:
        return {
            "score": BASELINE_STABILITY_SCORE,
            "center": BASELINE_STABILITY_SCORE,
            "delta_from_baseline": 0,
            "band": "baseline",
            "label": "Personal baseline (normal for them)",
            "factors": ["First visit — score anchored at 50 so later visits can show improvement or decline"],
        }

    c = normalize_checkin(checkin) if checkin else None
    if not c:
        return {
            "score": None,
            "center": BASELINE_STABILITY_SCORE,
            "delta_from_baseline": None,
            "band": "unknown",
            "label": "No check-in",
            "factors": [],
        }

    total = BASELINE_STABILITY_SCORE
    factors: list[str] = []

    for label, key, better, slightly, much in (
        ("Mobility", "mobility_vs_normal", 10, -10, -20),
        ("Mood", "mood_vs_normal", 8, -8, -16),
        ("Eating", "eating_vs_normal", 6, -6, -12),
    ):
        delta, tip = _vs_delta(c[key], better=better, slightly=slightly, much=much)
        if delta:
            total += delta
            factors.append(f"{label}: {tip} ({delta:+d})")

    overall_map = {
        "normal": (0, None),
        "minor_concern": (-8, "Overall: minor concern"),
        "significant_concern": (-18, "Overall: significant concern"),
        "emergency": (-35, "Overall: emergency"),
    }
    od, ot = overall_map.get(c["overall"], (0, None))
    if od:
        total += od
        factors.append(f"{ot} ({od:+d})")

    if c["mobility"] == "fall" or c["fallen_since_last"] == "yes":
        total -= 25
        factors.append("Fall reported (−25)")
    elif c["mobility"] == "significant_decline":
        total -= 12
        factors.append("Significant mobility decline (−12)")
    elif c["mobility"] == "slight_decline":
        total -= 6
        factors.append("Slight mobility decline (−6)")

    if c["unsteady"] == "yes":
        total -= 6
        factors.append("Unsteady (STEADI cue) (−6)")
    if c["worried_about_falling"] == "yes":
        total -= 4
        factors.append("Worried about falling (STEADI cue) (−4)")

    mood_map = {"normal": 0, "low": -5, "anxious": -5, "confused": -8}
    md = mood_map.get(c["mood"], 0)
    if md:
        total += md
        factors.append(f"Mood: {c['mood']} ({md:+d})")

    if c["eating"] == "reduced":
        total -= 5
        factors.append("Eating reduced (−5)")
    elif c["eating"] == "not_eating":
        total -= 12
        factors.append("Not eating (−12)")

    med_map = {"none": 0, "refill": -3, "missed": -8, "change": -4, "concern": -10}
    med = med_map.get(c["medication"], 0)
    if med:
        total += med
        factors.append(f"Medication: {c['medication']} ({med:+d})")

    contact_map = {
        "answered_normal": 0,
        "answered_confused": -8,
        "answered_distressed": -20,
        "requested_help": -22,
        "no_answer": -10,
    }
    cd = contact_map.get(c["contact_outcome"], 0)
    if cd:
        total += cd
        factors.append(f"Contact: {c['contact_outcome'].replace('_', ' ')} ({cd:+d})")

    if c["new_symptoms"] == "yes":
        total -= 8
        factors.append("New symptoms (−8)")
    if c["home_safety_issue"] == "yes":
        total -= 6
        factors.append("Home safety issue (−6)")
    if c["follow_up_required"] or c["new_request"] == "yes":
        total -= 3
        factors.append("Follow-up / open request (−3)")

    # Cap improvement when hard red flags present
    if c["overall"] == "emergency" or c["mobility"] == "fall" or c["fallen_since_last"] == "yes":
        total = min(total, 25)

    score = max(STABILITY_MIN, min(STABILITY_MAX, int(round(total))))
    delta = score - BASELINE_STABILITY_SCORE

    if score >= 65:
        band, label = "improved", "Above personal baseline"
    elif score >= 45:
        band, label = "stable", "Near personal baseline"
    elif score >= 30:
        band, label = "declining", "Below personal baseline"
    else:
        band, label = "critical", "Well below personal baseline"

    return {
        "score": score,
        "center": BASELINE_STABILITY_SCORE,
        "delta_from_baseline": delta,
        "band": band,
        "label": label,
        "factors": factors[:12],
    }

def checkin_summary_lines(checkin: dict) -> list[str]:
    lines: list[str] = []
    overall_map = {
        "normal": "Overall normal",
        "minor_concern": "Minor concern",
        "significant_concern": "Significant concern",
        "emergency": "Emergency — escalate",
    }
    lines.append(overall_map.get(checkin["overall"], "Check-in recorded"))
    if checkin["mobility"] == "fall":
        lines.append("Fall reported")
    elif checkin["mobility"] != "normal_for_them":
        lines.append(f"Mobility: {checkin['mobility'].replace('_', ' ')}")
    if checkin["mood"] != "normal":
        lines.append(f"Mood: {checkin['mood']}")
    if checkin["eating"] != "normal":
        lines.append(f"Eating: {checkin['eating'].replace('_', ' ')}")
    if checkin["medication"] != "none":
        lines.append(f"Medication: {checkin['medication']}")
    if checkin["new_symptoms"] == "yes":
        lines.append(checkin["symptoms_note"] or "New symptoms noted")
    if checkin["home_safety_issue"] == "yes":
        lines.append(checkin["home_safety_note"] or "Home safety issue")
    if checkin["new_request"] == "yes":
        lines.append(checkin["request_note"] or "New family request")
    if checkin["follow_up_required"]:
        lines.append("Follow-up required")
    note = checkin.get("family_message") or checkin.get("care_manager_note") or ""
    if note:
        lines.append(note[:180])
    return lines


def build_visit_summary_from_checkin(checkin: dict, free_summary: str = "") -> str:
    free = (free_summary or "").strip()
    if free:
        return free
    lines = checkin_summary_lines(checkin)
    return "; ".join(lines[:4]) if lines else "Wellness check-in completed"


def compute_care_status(
    *,
    visits: list[dict],
    open_service_requests: int = 0,
    open_incidents: int = 0,
    contact_stale_days: int = 7,
    baseline: dict | None = None,
    last_contact_at: datetime | None = None,
) -> dict:
    """Rule engine: RED hard flags first, then YELLOW, else GREEN if recent check-in.

    The status is read from the newest completed visit *that has a check-in*.
    A newer completed visit without one (an installation, a delivery) must not
    hide an earlier wellness check-in behind "awaiting baseline". When no visit
    carries a check-in but a baseline profile is stored, the baseline itself is
    the established normal and the status is OK with a note that no check-in
    has been recorded since it.
    """
    reasons: list[str] = []
    completed = []
    for raw in visits:
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("status") or "completed").lower()
        if status not in ("completed", "done"):
            continue
        checkin = normalize_checkin(raw.get("checkin"))
        visited = _parse_dt(raw.get("visited_at"))
        completed.append({"raw": raw, "checkin": checkin, "visited_at": visited})

    completed.sort(
        key=lambda r: r["visited_at"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    # Only visits with a check-in feed the rules; the rest are context.
    with_checkin = [row for row in completed if row["checkin"]]

    if open_incidents > 0:
        reasons.append("Open SOS / critical incident")
        return _status_payload(
            STATUS_RED,
            reasons,
            last_checkin=with_checkin[0] if with_checkin else None,
            open_service_requests=open_service_requests,
            open_incidents=open_incidents,
        )

    latest = with_checkin[0] if with_checkin else None
    if not latest:
        if is_baseline_established(baseline):
            base = normalize_baseline(baseline)
            since = _parse_dt(base.get("updated_at"))
            since_label = since.strftime("%d %b %Y") if since else "the baseline visit"
            return _status_payload(
                STATUS_GREEN,
                [
                    f"Baseline profile established — no wellness check-in recorded since {since_label}",
                ],
                last_checkin=None,
                open_service_requests=open_service_requests,
                open_incidents=open_incidents,
                confirmed_at=since,
                change_summary=(
                    "Their normal is on file. The next wellness check-in will "
                    "compare against it."
                ),
            )
        return _status_payload(
            STATUS_UNKNOWN,
            ["Awaiting baseline profile visit — first visit establishes their normal"],
            last_checkin=None,
            open_service_requests=open_service_requests,
            open_incidents=open_incidents,
        )

    c = latest["checkin"]
    visited = latest["visited_at"]

    # --- RED (hard-coded; AI must not soften these) ---
    if c["overall"] == "emergency":
        reasons.append("Care Manager marked emergency")
    if c["mobility"] == "fall" or c.get("fallen_since_last") == "yes":
        reasons.append("Fall reported on last check-in")
    if c["contact_outcome"] in ("answered_distressed", "requested_help"):
        reasons.append("Distressed or requested help on last contact")
    if c["new_symptoms"] == "yes" and c["overall"] in ("significant_concern", "emergency"):
        reasons.append("Significant new symptoms")
    if reasons:
        return _status_payload(
            STATUS_RED,
            reasons,
            last_checkin=latest,
            open_service_requests=open_service_requests,
            open_incidents=open_incidents,
        )

    # --- YELLOW ---
    yellow: list[str] = []
    if c["overall"] in ("minor_concern", "significant_concern"):
        yellow.append(f"Overall: {c['overall'].replace('_', ' ')}")
    if c["mobility"] in ("slight_decline", "significant_decline"):
        yellow.append(f"Mobility: {c['mobility'].replace('_', ' ')}")
    if c["mobility_vs_normal"] in ("slightly_worse", "much_worse"):
        yellow.append("Mobility worse than usual")
    if c.get("unsteady") == "yes" or c.get("worried_about_falling") == "yes":
        yellow.append("Unsteady or worried about falling (STEADI cue)")
    if c["mood"] in ("low", "anxious", "confused"):
        yellow.append(f"Mood: {c['mood']}")
    if c["mood_vs_normal"] in ("slightly_worse", "much_worse"):
        yellow.append("Mood worse than usual")
    if c["eating"] in ("reduced", "not_eating"):
        yellow.append(f"Eating: {c['eating'].replace('_', ' ')}")
    if c["medication"] != "none":
        yellow.append(f"Medication: {c['medication']}")
    if c["new_symptoms"] == "yes":
        yellow.append("New symptoms noted")
    if c["home_safety_issue"] == "yes":
        yellow.append("Home safety issue open")
    if c["follow_up_required"] or c["new_request"] == "yes":
        yellow.append("Follow-up / open request")
    if c["contact_outcome"] == "no_answer":
        yellow.append("Last contact unanswered")
    if c["contact_outcome"] == "answered_confused":
        yellow.append("Sounded confused on last contact")
    if open_service_requests > 0:
        yellow.append(f"{open_service_requests} open family request(s)")
    # Contact = the newest completed visit of any kind (a care visit without a
    # check-in still counts), not just the newest check-in.
    contact = visited
    for when in [completed[0]["visited_at"] if completed else None, _parse_dt(last_contact_at)]:
        if when is not None:
            when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
            if contact is None or when > (contact if contact.tzinfo else contact.replace(tzinfo=timezone.utc)):
                contact = when
    if contact:
        age = _now() - (contact if contact.tzinfo else contact.replace(tzinfo=timezone.utc))
        if age > timedelta(days=contact_stale_days):
            yellow.append(f"No confirmed contact in {contact_stale_days}+ days")

    # Two consecutive mobility declines → attention
    declines = 0
    for row in with_checkin[:3]:
        ci = row["checkin"]
        if not ci:
            continue
        if ci["mobility"] in ("slight_decline", "significant_decline", "fall") or ci[
            "mobility_vs_normal"
        ] in ("slightly_worse", "much_worse"):
            declines += 1
    if declines >= 2:
        yellow.append("Mobility marked worse on multiple recent visits")

    if yellow:
        return _status_payload(
            STATUS_YELLOW,
            yellow,
            last_checkin=latest,
            open_service_requests=open_service_requests,
            open_incidents=open_incidents,
        )

    return _status_payload(
        STATUS_GREEN,
        ["Recent successful check-in", "No significant new concerns reported"],
        last_checkin=latest,
        open_service_requests=open_service_requests,
        open_incidents=open_incidents,
    )


def _status_payload(
    level: str,
    reasons: list[str],
    *,
    last_checkin: dict | None,
    open_service_requests: int,
    open_incidents: int,
    confirmed_at: datetime | None = None,
    change_summary: str | None = None,
) -> dict:
    checkin = last_checkin["checkin"] if last_checkin else None
    visited = (last_checkin["visited_at"] if last_checkin else None) or confirmed_at
    raw = last_checkin["raw"] if last_checkin else {}
    snapshot = {
        "overall": checkin["overall"] if checkin else None,
        "mood": checkin["mood"] if checkin else None,
        "mobility": checkin["mobility"] if checkin else None,
        "eating": checkin["eating"] if checkin else None,
        "medication": checkin["medication"] if checkin else None,
        "falls": "reported" if checkin and checkin["mobility"] == "fall" else "none_reported",
        "home_safety": (
            "issue"
            if checkin and checkin["home_safety_issue"] == "yes"
            else ("ok" if checkin else None)
        ),
        "open_request": (
            checkin.get("request_note")
            if checkin and (checkin["new_request"] == "yes" or checkin["follow_up_required"])
            else None
        ),
        "staff_name": (raw.get("staff_name") or None) if raw else None,
        "care_manager_note": (
            (checkin.get("family_message") or checkin.get("care_manager_note") or None)
            if checkin
            else None
        ),
        "family_message": (
            (checkin.get("family_message") or checkin.get("care_manager_note") or None)
            if checkin
            else (str(raw.get("family_message") or "").strip() or None)
        ),
    }
    change = change_summary or _change_blurb(level, reasons, checkin)
    return {
        "level": level,
        "label": STATUS_LABELS[level],
        "headline_suffix": STATUS_FAMILY_HEADLINES[level],
        "reasons": reasons[:8],
        "confirmed_at": visited.isoformat() if visited else None,
        "snapshot": snapshot,
        "change_summary": change,
        "open_service_requests": open_service_requests,
        "open_incidents": open_incidents,
        "disclaimer": "Care coordination status from recent check-ins — not a medical diagnosis.",
        "computed_at": _now().isoformat(),
    }


def _change_blurb(level: str, reasons: list[str], checkin: dict | None) -> str:
    if level == STATUS_UNKNOWN:
        return "Care Manager will establish a baseline profile on the first visit."
    if level == STATUS_GREEN:
        return "No significant change from the previous check-in pattern."
    if level == STATUS_RED:
        return "Urgent follow-up is underway. Contact your Care Manager if you need details."
    # yellow
    tip = reasons[0] if reasons else "Something needs follow-up"
    extra = ""
    if checkin and checkin.get("mobility_vs_normal") in ("slightly_worse", "much_worse"):
        extra = " Consider a mobility / physiotherapy reassessment if this continues."
    return f"Attention recommended: {tip}.{extra}"


def family_status_report(status: dict, *, senior_name: str) -> dict:
    first = (senior_name or "Your parent").split()[0] or "Your parent"
    suffix = status.get("headline_suffix") or STATUS_FAMILY_HEADLINES.get(
        status.get("level"), ""
    )
    headline = f"{first} {suffix}".replace("  ", " ").strip()
    return {
        **status,
        "senior_first_name": first,
        "headline": headline,
    }


def publish_wellness_from_visit(block: dict, visit: dict) -> dict:
    """Append a family-visible wellness report from a completed check-in visit."""
    checkin = normalize_checkin(visit.get("checkin"))
    highlights = checkin_summary_lines(checkin) if checkin else []
    family_message = (
        str(visit.get("family_message") or "").strip()
        or (checkin.get("family_message") if checkin else "")
        or (checkin.get("care_manager_note") if checkin else "")
        or ""
    )
    summary = (visit.get("summary") or "").strip() or (
        "; ".join(highlights[:3]) if highlights else "Visit completed"
    )
    reports = list(block.get("wellness_reports") or [])
    if not isinstance(reports, list):
        reports = []
    reports.insert(
        0,
        {
            "id": f"wr_{visit.get('id', '')}",
            "date": visit.get("visited_at") or _now().isoformat(),
            "visit_type": visit.get("visit_type") or "Wellness visit",
            "summary": summary,
            "family_message": family_message or None,
            "assessor_name": visit.get("staff_name") or None,
            "highlights": highlights[:8],
        },
    )
    block["wellness_reports"] = reports[:40]
    return block


def save_care_status(block: dict, status: dict) -> dict:
    block["care_status"] = {
        "level": status["level"],
        "label": status["label"],
        "headline_suffix": status["headline_suffix"],
        "reasons": status["reasons"],
        "confirmed_at": status["confirmed_at"],
        "snapshot": status["snapshot"],
        "change_summary": status["change_summary"],
        "open_service_requests": status["open_service_requests"],
        "open_incidents": status["open_incidents"],
        "disclaimer": status["disclaimer"],
        "computed_at": status["computed_at"],
    }
    return block


def get_baseline(block: dict) -> dict:
    return normalize_baseline(block.get("care_baseline") if isinstance(block, dict) else None)


def set_baseline(block: dict, raw: dict | None, *, source_visit_id: str | None = None) -> dict:
    base = normalize_baseline(raw)
    base["updated_at"] = _now().isoformat()
    if source_visit_id:
        base["source_visit_id"] = str(source_visit_id)
    block["care_baseline"] = base
    return block
