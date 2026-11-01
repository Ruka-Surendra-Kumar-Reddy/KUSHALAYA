"""Plain family-facing wording for device alerts.

Staff see device ids, hub keys and MAC addresses on the incident row. Families
never should: they get one plain sentence. ``sanitize_family_alert`` also
rewrites rows written before this existed, on the way out.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

FAMILY_DEVICE_TITLES = {
    "SOS_BUTTON": "SOS from the alert band",
    "FALL_SUSPECTED": "Possible fall",
    "IMMOBILITY_WARNING": "No movement noticed",
    "DEVICE_OFFLINE": "Alert band not checking in",
    "BATTERY_LOW": "Alert band battery low",
}

# Prefixes the old (staff-style) bodies started with -> event type.
_LEGACY_PREFIXES = (
    ("Wearable SOS", "SOS_BUTTON"),
    ("Possible fall", "FALL_SUSPECTED"),
    ("Immobility warning", "IMMOBILITY_WARNING"),
    ("Wearable offline", "DEVICE_OFFLINE"),
    ("Wearable battery low", "BATTERY_LOW"),
)
_LEGACY_TITLES = (
    ("SOS from wearable", "SOS_BUTTON"),
    ("Possible fall from wearable", "FALL_SUSPECTED"),
    ("No motion from wearable", "IMMOBILITY_WARNING"),
    ("Wearable not heard", "DEVICE_OFFLINE"),
    ("Wearable battery low", "BATTERY_LOW"),
)

_CODE_RE = re.compile(r"\s*(?:·\s*)?\b(?:device|hub|mac)=\S+", re.I)
_MAC_RE = re.compile(r"\b(?:[0-9A-F]{2}[:-]){5}[0-9A-F]{2}\b", re.I)


def _possessive(name: str | None) -> str:
    n = (name or "").strip()
    if not n:
        return "Your family member's"
    return f"{n}'" if n.endswith("s") else f"{n}'s"


def _day(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    d = dt.astimezone(IST)
    return f"{d.day} {d.strftime('%b')}"


def family_device_alert(
    event_type: str, elder_name: str | None, *, last_seen: datetime | None = None
) -> tuple[str, str]:
    """(title, body) for a device event, with no device codes."""
    who = _possessive(elder_name)
    name = (elder_name or "").strip() or "Your family member"
    et = str(event_type or "").upper()
    if et == "DEVICE_OFFLINE":
        since = _day(last_seen)
        when = f" since {since}" if since else " for a while"
        body = f"{who} alert band hasn't checked in{when} — it may need charging or be out of range."
    elif et == "BATTERY_LOW":
        body = f"{who} alert band is running low on battery — please charge it today."
    elif et == "FALL_SUSPECTED":
        body = (
            f"{who} alert band noticed what may have been a fall. Please check on {name}, "
            "or call the care team."
        )
    elif et == "IMMOBILITY_WARNING":
        body = f"{who} alert band hasn't sensed movement for a while. Please check in with {name}."
    else:
        body = f"{name} pressed SOS on the alert band. The care team has been told."
    return FAMILY_DEVICE_TITLES.get(et, FAMILY_DEVICE_TITLES["SOS_BUTTON"]), body


def _legacy_event(title: str, body: str) -> str | None:
    for prefix, et in _LEGACY_PREFIXES:
        if body.startswith(prefix) and (" · " in body or "device=" in body or "mac=" in body
                                         or "BLE" in body or "accelerometer" in body):
            return et
    for prefix, et in _LEGACY_TITLES:
        if title.startswith(prefix):
            return et
    return None


def strip_device_codes(text: str) -> str:
    out = _CODE_RE.sub("", text or "")
    out = _MAC_RE.sub("", out)
    return re.sub(r"\s{2,}", " ", out).strip(" ·")


def sanitize_family_alert(
    title: str, body: str, *, elder_name: str | None = None, created_at: datetime | None = None
) -> tuple[str, str]:
    """Rewrite a stored alert (old rows included) so no device codes reach families."""
    t = str(title or "")
    b = str(body or "")
    et = _legacy_event(t, b)
    if et:
        return family_device_alert(et, elder_name, last_seen=created_at)
    return strip_device_codes(t) or t, strip_device_codes(b)


_PATHWAY_RE = re.compile(r"(?im)^[ \t]*(?:Suggested pathway|Pathway):[^\n]*\n?")
_PATHWAY_INLINE_RE = re.compile(r"[ \t]*Suggested pathway:[^.\n]*\.?")
# Old publishes stored "LiveWell360 Independence Score™"; the product is now the Safety Score.
_OLD_SCORE_RE = re.compile(
    r"(?:\b(?:LiveWell360|KushAlaya|Kushalaya)\s*™?\s*)?Independence Score™?"
)


def clean_family_summary(text: str | None) -> str | None:
    """Family-facing score summary: no internal pathway / membership names."""
    if text is None:
        return None
    from app.livewell.brand import safety_score_name

    out = _OLD_SCORE_RE.sub(safety_score_name(), str(text))
    out = _PATHWAY_INLINE_RE.sub("", out)
    out = _PATHWAY_RE.sub("", out)
    out = out.replace("Focus domains:", "Areas to focus on:")
    return re.sub(r"[ \t]{2,}", " ", out).strip()


_SAFE_STATE_RE = re.compile(r"^(.*?)\s+(installed|fitted|present|available|in place)$", re.I)


# Problem words for labels that don't follow "<thing> installed" (lower-case keys).
# Same rows as FINDING_WORDS in frontend/lib/livewell/familyFindings.ts.
FINDING_WORDS: dict[str, str] = {
    "anti-slip flooring": "Slippery floors",
    "slip-resistant floor": "Slippery floors",
    "slip resistance": "Slippery floors",
    "floor dry": "Wet floors",
    "pathway level and clear": "Uneven or cluttered pathway",
    "clear pathway": "Cluttered pathway",
    "walkway clear": "Cluttered walkway",
    "living area walkways clear": "Cluttered walkways in the living area",
    "hallways free of trip hazards": "Trip hazards in the hallways",
    "trip hazards removed": "Trip hazards",
    "wheelchair or walker path clear": "No clear path for the walker or wheelchair",
    "loose rugs secured or removed": "Loose rugs",
    "loose rugs removed": "Loose rugs",
    "emergency contacts posted": "No emergency contacts posted",
    "emergency contacts displayed": "No emergency contacts posted",
    "bedroom night lighting": "No bedroom night light",
    "night light": "No night light",
    "night lamp": "No night lamp",
    "adequate entry lighting": "Entrance too dark",
    "adequate lighting": "Too dark",
    "lighting adequate": "Too dark",
    "light switches easy to reach and operate": "Light switches hard to reach",
    "toilet height appropriate": "Toilet too low or too high",
    "chair height appropriate": "Chair too low or too high",
    "bed height": "Bed too low or too high",
    "shower threshold safe": "Unsafe shower step",
    "door widths / thresholds accessible": "Narrow doors or raised thresholds",
    "zero-step or ramped main entry": "Steps at the main entrance",
    "entrance railing if needed": "No railing at the entrance",
    "stairs manageable or alternative exists": "Stairs are hard to manage",
    "smoke and co detectors on each level": "No smoke or gas alarm on each floor",
    "hot water scald risk controlled": "Hot water can scald",
    "water temperature safe": "Hot water can scald",
    "electrical outlets/wiring safe": "Unsafe sockets or wiring",
    "stove / gas safety controls": "Stove or gas not safe",
    "sos / alert method available": "No way to call for help",
    "can use phone for emergencies": "Can't use the phone in an emergency",
    "first aid / flashlight accessible": "No first-aid kit or torch to hand",
    "evacuation path understood": "No clear way out in an emergency",
    "family response plan documented": "No family emergency plan",
    "bathroom well ventilated": "Bathroom poorly ventilated",
    "damp / mold controlled": "Damp or mould",
    "no major structural hazards": "Structural hazards in the home",
    "home secure (locks, visitor check)": "Home not secure",
    "steady when walking": "Unsteady when walking",
    "balance adequate for home": "Poor balance",
    "transfers bed/chair safely": "Unsafe getting in and out of bed or chairs",
    "bed transfer support": "Hard to get in and out of bed",
    "stands from chair without arm push": "Needs arms to stand from a chair",
    "no falls in the past year": "Had a fall in the past year",
    "not worried about falling": "Worried about falling",
}


def finding_problem(label: str) -> str:
    """Rubric labels name the safe state ("Toilet grab bar installed"); say the
    problem instead ("No toilet grab bar"). Mirrors findingProblem in
    frontend lib/livewell/familyFindings.ts."""
    t = str(label or "").strip()
    mapped = FINDING_WORDS.get(t.lower())
    if mapped:
        return mapped
    m = _SAFE_STATE_RE.match(t)
    if m:
        thing = m.group(1)
        if not re.match(r"^[A-Z]{2,}", thing):
            thing = thing[:1].lower() + thing[1:]
        return f"No {thing}"
    return f"{t} — needs fixing" if t else t
