import math
from dataclasses import dataclass

from app.models.caregiver import Caregiver
from app.models.caregiver_skill import CaregiverSkill
from app.models.elder import Elder
from app.models.elder_requirement import ElderRequirement
from app.models.skill import Skill


@dataclass(frozen=True)
class ScoringWeights:
    skill: float = 40.0
    experience: float = 15.0
    language: float = 10.0
    location: float = 10.0
    availability: float = 10.0
    verification: float = 5.0
    ratings: float = 5.0
    historical: float = 5.0


WEIGHTS = ScoringWeights()

VERIFIED_STATUSES = {"VERIFIED", "APPROVED", "COMPLETE", "COMPLETED"}


def _attrs(entity) -> dict:
    return entity.custom_attributes or {}


def score_skill(
    requirements: list[ElderRequirement],
    caregiver_skills: list[CaregiverSkill],
    skills_by_id: dict[int, Skill],
) -> tuple[float, list[str]]:
    if not requirements:
        return 1.0, []

    caregiver_skill_ids = {cs.skill_id for cs in caregiver_skills}
    matched_weight = 0.0
    total_weight = 0.0
    reasons: list[str] = []

    for req in requirements:
        if not req.required:
            continue
        weight = req.weight or 1
        total_weight += weight
        if req.skill_id in caregiver_skill_ids:
            matched_weight += weight
            skill = skills_by_id.get(req.skill_id)
            if skill:
                reasons.append(f"Skill: {skill.name}")

    if total_weight == 0:
        return 1.0, reasons

    return matched_weight / total_weight, reasons


def score_experience(elder: Elder, caregiver: Caregiver) -> tuple[float, list[str]]:
    required = float(_attrs(elder).get("required_experience_years") or 0)
    actual = float(caregiver.years_experience or 0)

    if required <= 0:
        return 1.0, [f"{int(actual)} years experience"] if actual else []

    if actual <= 0:
        score = 0.0
    else:
        ratio = actual / required
        score = min(1.0, max(0.2, ratio))

    reasons = []
    if actual:
        reasons.append(f"{int(actual)} years experience")
    return min(1.0, score), reasons


def score_language(elder: Elder, caregiver: Caregiver) -> tuple[float, list[str]]:
    preference = _attrs(elder).get("language_preference")
    languages = _attrs(caregiver).get("languages") or []

    if not preference:
        return 1.0, []

    if isinstance(preference, str):
        preferences = [preference.lower()]
    else:
        preferences = [str(p).lower() for p in preference]

    caregiver_langs = [str(lang).lower() for lang in languages]

    if not caregiver_langs:
        return 0.0, []

    matches = [p for p in preferences if p in caregiver_langs]
    if matches:
        return 1.0, [f"{m.title()} speaking" for m in matches]

    overlap = len(set(preferences) & set(caregiver_langs))
    if overlap:
        return 0.5, ["Partial language match"]

    return 0.0, []


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def score_location(elder: Elder, caregiver: Caregiver) -> tuple[float, list[str]]:
    elder_attrs = _attrs(elder)
    caregiver_attrs = _attrs(caregiver)

    try:
        e_lat = float(elder_attrs["latitude"])
        e_lon = float(elder_attrs["longitude"])
        c_lat = float(caregiver_attrs["latitude"])
        c_lon = float(caregiver_attrs["longitude"])
    except (KeyError, TypeError, ValueError):
        return 0.5, []

    km = _haversine_km(e_lat, e_lon, c_lat, c_lon)

    if km <= 5:
        score = 1.0
    elif km <= 10:
        score = 0.8
    elif km <= 20:
        score = 0.6
    else:
        score = 0.3

    return score, [f"{km:.1f} km from elder"]


def score_availability(elder: Elder, caregiver: Caregiver) -> tuple[float, list[str]]:
    elder_schedule = _attrs(elder).get("schedule_requirements")
    caregiver_avail = _attrs(caregiver).get("availability")
    care_type = _attrs(elder).get("care_type")

    if not elder_schedule and not care_type:
        return 1.0, []

    if not caregiver_avail:
        return 0.5, []

    score = 1.0
    reasons: list[str] = []

    if care_type:
        care_types = caregiver_avail.get("care_types") or []
        if care_type in care_types or care_type == caregiver_avail.get("care_type"):
            reasons.append(f"{care_type.replace('_', ' ').title()} available")
        else:
            score = min(score, 0.3)

    elder_days = set(elder_schedule.get("days", [])) if isinstance(elder_schedule, dict) else set()
    caregiver_days = set(caregiver_avail.get("days", [])) if isinstance(caregiver_avail, dict) else set()

    if elder_days and caregiver_days:
        overlap = elder_days & caregiver_days
        if overlap:
            score = min(1.0, score * (len(overlap) / len(elder_days)))
            reasons.append("Schedule compatible")
        else:
            score = min(score, 0.2)

    return score, reasons


def score_verification(
    caregiver: Caregiver,
    caregiver_skills: list[CaregiverSkill],
) -> tuple[float, list[str]]:
    checks = 0
    passed = 0
    reasons: list[str] = []

    for label, status in (
        ("Police verified", caregiver.police_verification_status),
        ("Background verified", caregiver.background_check_status),
    ):
        checks += 1
        if status and status.upper() in VERIFIED_STATUSES:
            passed += 1
            reasons.append(label)

    checks += 1
    if any(cs.certified for cs in caregiver_skills):
        passed += 1
        reasons.append("Certification verified")

    if checks == 0:
        return 0.0, reasons

    return passed / checks, reasons


def score_ratings(
    caregiver: Caregiver,
    db_ratings: list[float],
) -> tuple[float, list[str]]:
    values = list(db_ratings)
    avg_attr = _attrs(caregiver).get("average_rating")
    if avg_attr is not None:
        values.append(float(avg_attr))

    if not values:
        return 0.5, []

    avg = sum(values) / len(values)
    normalized = min(1.0, avg / 5.0)
    return normalized, [f"{avg:.1f} rating"]


def score_historical(
    completion_rate: float | None,
    incident_penalty: float,
) -> tuple[float, list[str]]:
    if completion_rate is None:
        return 0.5, []

    base = completion_rate
    score = max(0.0, min(1.0, base - incident_penalty))
    reasons = []
    if completion_rate >= 0.8:
        reasons.append("Strong placement history")
    return score, reasons


def score_caregiver(
    elder: Elder,
    caregiver: Caregiver,
    requirements: list[ElderRequirement],
    caregiver_skills: list[CaregiverSkill],
    skills_by_id: dict[int, Skill],
    db_ratings: list[float],
    completion_rate: float | None,
    incident_count: int,
) -> dict:
    incident_penalty = min(0.3, incident_count * 0.05)

    components: dict[str, float] = {}
    all_reasons: list[str] = []

    skill_s, skill_r = score_skill(requirements, caregiver_skills, skills_by_id)
    components["skill"] = round(skill_s * WEIGHTS.skill, 2)
    all_reasons.extend(skill_r)

    exp_s, exp_r = score_experience(elder, caregiver)
    components["experience"] = round(exp_s * WEIGHTS.experience, 2)
    all_reasons.extend(exp_r)

    lang_s, lang_r = score_language(elder, caregiver)
    components["language"] = round(lang_s * WEIGHTS.language, 2)
    all_reasons.extend(lang_r)

    loc_s, loc_r = score_location(elder, caregiver)
    components["location"] = round(loc_s * WEIGHTS.location, 2)
    all_reasons.extend(loc_r)

    avail_s, avail_r = score_availability(elder, caregiver)
    components["availability"] = round(avail_s * WEIGHTS.availability, 2)
    all_reasons.extend(avail_r)

    ver_s, ver_r = score_verification(caregiver, caregiver_skills)
    components["verification"] = round(ver_s * WEIGHTS.verification, 2)
    all_reasons.extend(ver_r)

    rat_s, rat_r = score_ratings(caregiver, db_ratings)
    components["ratings"] = round(rat_s * WEIGHTS.ratings, 2)
    all_reasons.extend(rat_r)

    hist_s, hist_r = score_historical(completion_rate, incident_penalty)
    components["historical"] = round(hist_s * WEIGHTS.historical, 2)
    all_reasons.extend(hist_r)

    total = round(sum(components.values()), 2)
    confidence = round(min(1.0, 0.5 + total / 200), 2)

    return {
        "caregiver_id": caregiver.id,
        "caregiver_name": f"{caregiver.first_name} {caregiver.last_name}",
        "match_score": total,
        "confidence_score": confidence,
        "component_scores": components,
        "reasons": all_reasons[:8],
    }
