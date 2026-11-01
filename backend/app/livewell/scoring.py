"""Server-side Independence Score™ — mirrors frontend/lib/livewell/assessment.ts.

Arithmetic (must stay identical to the frontend):
  * excellent (pass)    = maxPoints
  * acceptable (partial)= round(maxPoints * 0.5, 1)
  * unsafe (fail)       = 0
  * na                  = excluded from numerator AND denominator
  * unrated (null)      = 0 earned, still counted in the denominator
  * Independence Score  = round(earned / max * 100)   (JS Math.round — half up)
  * Domain score        = same per applicable category

Applicability (skipWhen rules) mirrors conditional.ts / conditional-rules.ts.

Critical items: an item on the ``critical`` scoring scale earns points exactly
like a standard item, but if it is rated unsafe the Independence *band* is capped
at High Risk (see rule_engine_defaults.risk_band_for_score). The numeric score is
not changed.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from app.livewell.rubric_service import normalize_rubric
from app.livewell.stored_config import read_stored_config

_DEFAULT_RUBRIC_FILE = Path(__file__).resolve().parent / "default_rubric.json"

# Keys that make up the locked "content" of a completed assessment. Everything
# else (ids, timestamps, photos, quote/PO, family-publish stamps) may change
# without a reopen.
CONTENT_KEYS: tuple[str, ...] = (
    "clientFirstName",
    "clientLastName",
    "clientAddress",
    "clientPhone",
    "clientEmail",
    "familyContactName",
    "familyContactPhone",
    "painPoints",
    "assessorName",
    "notes",
    "residentProfile",
    "ratings",
    "itemNotes",
)


# ---------------------------------------------------------------------------
# Rubric
# ---------------------------------------------------------------------------
def _load_default_rubric_exact() -> list[dict]:
    """Default rubric with the exact fractional weights the frontend uses.

    ``rubric_defaults.DEFAULT_RUBRIC`` runs through normalize_rubric, which
    coerces maxPoints to integers >= 1 — that is right for tenant-saved rubrics
    (the frontend rounds those the same way) but wrong for the factory rubric,
    whose weights are fractional and sum to 100.
    """
    with _DEFAULT_RUBRIC_FILE.open(encoding="utf-8") as f:
        raw = json.load(f)
    out: list[dict] = []
    for cat in raw.get("categories") or []:
        items = []
        for item in cat.get("items") or []:
            row = {
                "id": str(item.get("id") or ""),
                "label": str(item.get("label") or ""),
                "maxPoints": float(item.get("maxPoints") or 0),
                "scoringScale": str(item.get("scoringScale") or "standard"),
            }
            if item.get("skipWhen"):
                row["skipWhen"] = item["skipWhen"]
            if item.get("group"):
                row["group"] = item["group"]
            items.append(row)
        out.append(
            {
                "id": str(cat.get("id") or ""),
                "title": str(cat.get("title") or ""),
                "sectionNumber": cat.get("sectionNumber"),
                "maxPoints": float(cat.get("maxPoints") or sum(i["maxPoints"] for i in items)),
                "items": items,
                **({"skipWhen": cat["skipWhen"]} if cat.get("skipWhen") else {}),
            }
        )
    return out


_DEFAULT_RUBRIC_CACHE: list[dict] | None = None


def default_rubric_categories() -> list[dict]:
    global _DEFAULT_RUBRIC_CACHE
    if _DEFAULT_RUBRIC_CACHE is None:
        _DEFAULT_RUBRIC_CACHE = _load_default_rubric_exact()
    return _DEFAULT_RUBRIC_CACHE


def effective_rubric(workflow_config: dict | None) -> tuple[list[dict], str]:
    """(categories, source) — tenant rubric when saved, else the factory rubric."""
    stored = read_stored_config(workflow_config or {}).get("rubric") or {}
    normalized = normalize_rubric(stored) if stored.get("categories") else {"categories": []}
    if normalized["categories"]:
        return normalized["categories"], "tenant"
    return default_rubric_categories(), "default"


# ---------------------------------------------------------------------------
# Conditional rules (conditional-rules.ts)
# ---------------------------------------------------------------------------
def _has_assistive_device(profile: dict) -> bool:
    d = profile.get("mobilityDevice")
    return bool(d and d != "none")


def _is_ramp_relevant(profile: dict) -> bool:
    return profile.get("hasStairs") is True or profile.get("mobilityDevice") == "wheelchair"


def evaluate_conditional_rule(rule_id: str, profile: dict) -> bool:
    """True when the item/section should be skipped (hidden)."""
    if rule_id == "unless_has_stairs":
        return profile.get("hasStairs") is not True
    if rule_id == "unless_wheelchair_user":
        return profile.get("mobilityDevice") != "wheelchair"
    if rule_id == "unless_lives_alone":
        return profile.get("livesAlone") is not True
    if rule_id == "unless_smart_home_advanced":
        return profile.get("smartHomeAdvanced") is not True
    if rule_id == "unless_has_balcony":
        return profile.get("hasBalcony") is not True
    if rule_id == "unless_domestic_helper":
        return profile.get("domesticHelper") is not True
    if rule_id == "unless_full_time_caregiver":
        return profile.get("fullTimeCaregiver") is not True
    if rule_id == "unless_assistive_device":
        return not _has_assistive_device(profile)
    if rule_id == "unless_ramp_relevant":
        return not _is_ramp_relevant(profile)
    return False


def matches_skip_rule(rule: dict | None, profile: dict) -> bool:
    if not rule or not isinstance(rule, dict):
        return False
    if rule.get("when"):
        return evaluate_conditional_rule(str(rule["when"]), profile)
    if rule.get("field"):
        value = profile.get(str(rule["field"]))
        if "equals" in rule:
            return value == rule["equals"]
        if "notEquals" in rule:
            return value != rule["notEquals"]
    return False


def is_hidden_unanswered(item: dict, ratings: dict | None) -> bool:
    """Hidden questions are not asked on new assessments; an old assessment
    that answered one keeps it (so its report still renders)."""
    if not item.get("hidden"):
        return False
    return normalize_rating((ratings or {}).get(item.get("id"))) is None


# Questions added to the rubric after assessments already existed (rubric_gap_fixes,
# 2026-10-11). Same map in frontend lib/livewell/conditional.ts. An item may also carry
# its own ``addedOn`` (YYYY-MM-DD).
QUESTIONS_ADDED_ON: dict[str, str] = {
    "home_safety_bathroom_well_ventilated": "2026-10-11",
    "health_wellness_bp_sugar_checked_regularly": "2026-10-11",
    "cognitive_emotional_safe_from_wandering_getting_lost": "2026-10-11",
    "technology_light_switches_easy_to_reach_and_operate": "2026-10-11",
    "technology_home_secure_locks_visitor_check": "2026-10-11",
}


def _is_completed(payload: dict) -> bool:
    status = str(payload.get("status") or "").strip().lower()
    return status == "completed" or bool(payload.get("completedAt"))


def categories_for_payload(categories: list[dict], payload: dict | None) -> list[dict]:
    """On a completed assessment, a question added after it was started and left
    unanswered was never asked: mark it hidden so it is left out of earned points and
    section totals (same as hidden-unanswered). Drafts are unchanged, so they still
    show and count the new questions."""
    payload = payload if isinstance(payload, dict) else {}
    if not _is_completed(payload):
        return categories
    started = str(payload.get("createdAt") or "")[:10]
    ratings = payload.get("ratings") if isinstance(payload.get("ratings"), dict) else {}
    out: list[dict] = []
    for cat in categories:
        items = []
        for item in cat.get("items") or []:
            added = str(item.get("addedOn") or QUESTIONS_ADDED_ON.get(str(item.get("id") or "")) or "")
            if (
                added
                and not item.get("hidden")
                and (not started or started < added)
                and normalize_rating(ratings.get(item.get("id"))) is None
            ):
                item = {**item, "hidden": True}
            items.append(item)
        out.append({**cat, "items": items})
    return out


def applicable_categories(categories: list[dict], profile: dict) -> list[dict]:
    out: list[dict] = []
    for cat in categories:
        if matches_skip_rule(cat.get("skipWhen"), profile):
            continue
        items = [i for i in cat.get("items") or [] if not matches_skip_rule(i.get("skipWhen"), profile)]
        if not items:
            continue
        out.append({**cat, "items": items})
    return out


# ---------------------------------------------------------------------------
# Ratings
# ---------------------------------------------------------------------------
def normalize_rating(rating: Any) -> str | None:
    if rating is None:
        return None
    r = str(rating).strip().lower()
    if r == "pass":
        return "excellent"
    if r == "partial":
        return "acceptable"
    if r == "fail":
        return "unsafe"
    if r in ("excellent", "acceptable", "unsafe", "na"):
        return r
    return None


def js_round(value: float) -> int:
    """JavaScript Math.round — halves round toward +infinity."""
    return int(math.floor(value + 0.5))


def item_points(rating: Any, max_points: float, scale: str = "standard") -> float:
    r = normalize_rating(rating)
    if r is None or r == "na":
        return 0.0
    if r == "excellent":
        return float(max_points)
    if r == "acceptable":
        return js_round(max_points * 0.5 * 10) / 10
    return 0.0


def profile_from_payload(payload: dict) -> dict:
    profile = payload.get("residentProfile")
    return profile if isinstance(profile, dict) else {}


def score_assessment(payload: dict, categories: list[dict]) -> dict:
    """Compute score + domain scores + critical findings from ratings."""
    profile = profile_from_payload(payload)
    ratings = payload.get("ratings") if isinstance(payload.get("ratings"), dict) else {}
    categories = categories_for_payload(categories, payload)
    earned_total = 0.0
    max_total = 0.0
    rated = 0
    domains: list[dict] = []
    critical: list[dict] = []
    for cat in applicable_categories(categories, profile):
        earned = 0.0
        max_pts = 0.0
        for item in cat["items"]:
            rating = ratings.get(item["id"])
            r = normalize_rating(rating)
            if is_hidden_unanswered(item, ratings):
                # Hidden question never asked on this assessment — not part of its score.
                continue
            if r is not None:
                rated += 1
            if r == "na":
                continue
            mp = float(item.get("maxPoints") or 0)
            scale = str(item.get("scoringScale") or "standard")
            max_pts += mp
            earned += item_points(rating, mp, scale)
            if scale == "critical" and r == "unsafe":
                critical.append(
                    {
                        "id": item["id"],
                        "label": item.get("label") or item["id"],
                        "category": cat.get("title") or cat.get("id"),
                    }
                )
        earned_total += earned
        max_total += max_pts
        if max_pts <= 0:
            continue
        domains.append(
            {
                "id": cat["id"],
                "title": cat.get("title") or cat["id"],
                "score": js_round(earned / max_pts * 100),
                "max_points": max_pts,
                "earned_points": js_round(earned * 10) / 10,
            }
        )
    score = js_round(earned_total / max_total * 100) if max_total > 0 else 0
    return {
        "independence_score": score,
        "domain_scores": domains,
        "domain_score_map": {d["id"]: d["score"] for d in domains},
        "critical_unsafe": critical,
        "rated_count": rated,
        "earned": earned_total,
        "max": max_total,
    }


# ---------------------------------------------------------------------------
# Profile-derived flags (single source, mirrored in livewell-rules.ts)
# ---------------------------------------------------------------------------
def _flag(payload: dict, profile: dict, *keys: str):
    for key in keys:
        if payload.get(key) is not None:
            return payload.get(key)
        if profile.get(key) is not None:
            return profile.get(key)
    return None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "y")


def family_abroad_from_payload(payload: dict) -> bool:
    profile = profile_from_payload(payload)
    return _truthy(
        _flag(payload, profile, "familyAbroad", "family_abroad", "childrenAbroad", "children_abroad")
    )


def lives_alone_from_payload(payload: dict) -> bool:
    profile = profile_from_payload(payload)
    return _truthy(_flag(payload, profile, "livesAlone", "lives_alone"))


_COGNITIVE_CONDITION_TERMS = ("dementia", "alzheimer", "parkinson", "stroke")


def normalize_cognitive(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "mild" if value else "none"
    v = str(value).strip().lower()
    if not v or v in ("none", "no", "false", "0"):
        return "none"
    if v in ("high", "severe", "critical"):
        return "high"
    if v in ("moderate", "med", "medium"):
        return "moderate"
    return "mild"


def cognitive_risk_from_payload(payload: dict) -> str:
    """"none" | "mild" | "moderate" | "high".

    An explicit flag (cognitiveRisk / mildDementia / dementia) wins; otherwise a
    coarse signal from residentProfile.medicalConditions.
    """
    profile = profile_from_payload(payload)
    explicit = _flag(payload, profile, "cognitiveRisk", "cognitive_risk", "mildDementia", "dementia")
    if explicit is not None and str(explicit).strip() != "":
        return normalize_cognitive(explicit)
    conditions = profile.get("medicalConditions") or []
    if not isinstance(conditions, list):
        return "none"
    for c in conditions:
        lc = str(c).lower()
        if any(term in lc for term in _COGNITIVE_CONDITION_TERMS):
            return "mild"
    return "none"


# ---------------------------------------------------------------------------
# Lock / versions
# ---------------------------------------------------------------------------
def content_hash(payload: dict) -> str:
    content = {k: payload.get(k) for k in CONTENT_KEYS}
    blob = json.dumps(content, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
