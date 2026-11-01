import sys
import types
from types import SimpleNamespace

import pytest

for _mod, _names in (
    (
        "app.models.elder_requirement",
        {"ElderRequirement": type("ElderRequirement", (), {})},
    ),
    ("app.models.caregiver", {"Caregiver": type("Caregiver", (), {})}),
    ("app.models.caregiver_skill", {"CaregiverSkill": type("CaregiverSkill", (), {})}),
    ("app.models.elder", {"Elder": type("Elder", (), {})}),
    ("app.models.skill", {"Skill": type("Skill", (), {})}),
):
    if _mod not in sys.modules:
        try:
            __import__(_mod)
        except ModuleNotFoundError:
            m = types.ModuleType(_mod)
            for k, v in _names.items():
                setattr(m, k, v)
            sys.modules[_mod] = m

from app.services.matching.scoring import (
    WEIGHTS,
    _haversine_km,
    score_availability,
    score_caregiver,
    score_experience,
    score_historical,
    score_language,
    score_location,
    score_ratings,
    score_skill,
    score_verification,
)


def _elder(**attrs):
    return SimpleNamespace(custom_attributes=attrs or {})


def _caregiver(**kwargs):
    attrs = kwargs.pop("custom_attributes", {})
    return SimpleNamespace(
        id=kwargs.get("id", 1),
        first_name=kwargs.get("first_name", "Anita"),
        last_name=kwargs.get("last_name", "Rao"),
        years_experience=kwargs.get("years_experience", 0),
        police_verification_status=kwargs.get("police_verification_status"),
        background_check_status=kwargs.get("background_check_status"),
        custom_attributes=attrs,
    )


def test_score_skill_no_requirements():
    score, reasons = score_skill([], [], {})
    assert score == 1.0
    assert reasons == []


def test_score_skill_ignores_optional_requirements():
    req = SimpleNamespace(required=False, weight=10, skill_id=1)
    score, _ = score_skill([req], [], {})
    assert score == 1.0


def test_score_skill_full_and_partial_match():
    reqs = [
        SimpleNamespace(required=True, weight=2, skill_id=1),
        SimpleNamespace(required=True, weight=1, skill_id=2),
    ]
    skills = [SimpleNamespace(skill_id=1)]
    by_id = {1: SimpleNamespace(name="Nursing")}
    score, reasons = score_skill(reqs, skills, by_id)
    assert score == pytest.approx(2 / 3)
    assert "Nursing" in reasons[0]


def test_score_skill_none_matched():
    reqs = [SimpleNamespace(required=True, weight=1, skill_id=9)]
    score, reasons = score_skill(reqs, [], {})
    assert score == 0.0
    assert reasons == []


@pytest.mark.parametrize(
    "required,actual,expected",
    [
        (0, 0, 1.0),
        (0, 5, 1.0),
        (4, 0, 0.0),
        (4, 2, 0.5),
        (4, 4, 1.0),
        (4, 10, 1.0),
        (10, 1, 0.2),
    ],
)
def test_score_experience(required, actual, expected):
    elder = _elder(required_experience_years=required)
    caregiver = _caregiver(years_experience=actual)
    score, reasons = score_experience(elder, caregiver)
    assert score == pytest.approx(expected)
    if actual:
        assert any("years experience" in r for r in reasons)


def test_score_language_no_preference():
    score, reasons = score_language(_elder(), _caregiver())
    assert score == 1.0
    assert reasons == []


def test_score_language_match_string_and_list():
    elder = _elder(language_preference="English")
    caregiver = _caregiver(custom_attributes={"languages": ["english", "Hindi"]})
    score, reasons = score_language(elder, caregiver)
    assert score == 1.0
    assert reasons == ["English speaking"]

    elder2 = _elder(language_preference=["Telugu", "Hindi"])
    score2, reasons2 = score_language(elder2, caregiver)
    assert score2 == 1.0
    assert "Hindi speaking" in reasons2


def test_score_language_no_caregiver_langs():
    elder = _elder(language_preference="English")
    score, reasons = score_language(elder, _caregiver())
    assert score == 0.0
    assert reasons == []


def test_score_language_no_overlap():
    elder = _elder(language_preference="Tamil")
    caregiver = _caregiver(custom_attributes={"languages": ["English"]})
    score, _ = score_language(elder, caregiver)
    assert score == 0.0


def test_haversine_same_point_is_zero():
    assert _haversine_km(17.4, 78.4, 17.4, 78.4) == pytest.approx(0.0)


def test_haversine_known_hyderabad_distance():
    km = _haversine_km(17.3850, 78.4867, 17.4486, 78.3908)
    assert 10 < km < 20


def test_score_location_missing_coords():
    score, reasons = score_location(_elder(), _caregiver())
    assert score == 0.5
    assert reasons == []


@pytest.mark.parametrize(
    "clat,clon,min_score,max_score",
    [
        (17.4, 78.4, 1.0, 1.0),
        (17.45, 78.45, 0.8, 1.0),
        (17.55, 78.55, 0.3, 0.8),
        (18.5, 79.5, 0.3, 0.3),
    ],
)
def test_score_location_bands(clat, clon, min_score, max_score):
    elder = _elder(latitude=17.4, longitude=78.4)
    caregiver = _caregiver(custom_attributes={"latitude": clat, "longitude": clon})
    score, reasons = score_location(elder, caregiver)
    assert min_score <= score <= max_score
    assert "km from elder" in reasons[0]


def test_score_availability_no_constraints():
    score, _ = score_availability(_elder(), _caregiver())
    assert score == 1.0


def test_score_availability_missing_caregiver_avail():
    score, _ = score_availability(_elder(care_type="visit_based"), _caregiver())
    assert score == 0.5


def test_score_availability_care_type_and_days():
    elder = _elder(
        care_type="visit_based",
        schedule_requirements={"days": ["mon", "wed"]},
    )
    caregiver = _caregiver(
        custom_attributes={
            "availability": {
                "care_type": "visit_based",
                "days": ["mon", "wed", "fri"],
            }
        }
    )
    score, reasons = score_availability(elder, caregiver)
    assert score == 1.0
    assert any("Visit Based" in r or "available" in r.lower() for r in reasons)


def test_score_availability_mismatch_penalizes():
    elder = _elder(
        care_type="live_in",
        schedule_requirements={"days": ["sat"]},
    )
    caregiver = _caregiver(
        custom_attributes={"availability": {"care_type": "visit_based", "days": ["mon"]}}
    )
    score, _ = score_availability(elder, caregiver)
    assert score <= 0.3


def test_score_verification_all_pass():
    cg = _caregiver(
        police_verification_status="verified",
        background_check_status="APPROVED",
    )
    skills = [SimpleNamespace(certified=True)]
    score, reasons = score_verification(cg, skills)
    assert score == 1.0
    assert len(reasons) == 3


def test_score_verification_none_pass():
    score, reasons = score_verification(_caregiver(), [])
    assert score == pytest.approx(0.0)
    assert reasons == []


@pytest.mark.parametrize(
    "ratings,avg_attr,expected",
    [
        ([], None, 0.5),
        ([5, 5], None, 1.0),
        ([4], None, 0.8),
        ([], 5, 1.0),
        ([5], 5, 1.0),
        ([10], None, 1.0),
    ],
)
def test_score_ratings(ratings, avg_attr, expected):
    cg = _caregiver(custom_attributes={"average_rating": avg_attr} if avg_attr is not None else {})
    score, _ = score_ratings(cg, ratings)
    assert score == pytest.approx(expected)


@pytest.mark.parametrize(
    "rate,penalty,expected,has_reason",
    [
        (None, 0, 0.5, False),
        (1.0, 0, 1.0, True),
        (0.9, 0.05, 0.85, True),
        (0.5, 0, 0.5, False),
        (0.2, 0.3, 0.0, False),
        (0.8, 0, 0.8, True),
    ],
)
def test_score_historical(rate, penalty, expected, has_reason):
    score, reasons = score_historical(rate, penalty)
    assert score == pytest.approx(expected)
    assert bool(reasons) is has_reason


def test_score_caregiver_aggregates_components():
    elder = _elder(
        required_experience_years=2,
        language_preference="English",
        latitude=17.4,
        longitude=78.4,
        care_type="visit_based",
        schedule_requirements={"days": ["mon"]},
    )
    caregiver = _caregiver(
        id=44,
        years_experience=5,
        police_verification_status="VERIFIED",
        background_check_status="VERIFIED",
        custom_attributes={
            "languages": ["English"],
            "latitude": 17.41,
            "longitude": 78.41,
            "availability": {"care_type": "visit_based", "days": ["mon", "wed"]},
            "average_rating": 5,
        },
    )
    reqs = [SimpleNamespace(required=True, weight=1, skill_id=1)]
    skills = [SimpleNamespace(skill_id=1, certified=True)]
    result = score_caregiver(
        elder,
        caregiver,
        reqs,
        skills,
        {1: SimpleNamespace(name="Nursing")},
        [5.0],
        0.9,
        0,
    )
    assert result["caregiver_id"] == 44
    assert result["caregiver_name"] == "Anita Rao"
    assert result["match_score"] > 80
    assert set(result["component_scores"]) == {
        "skill",
        "experience",
        "language",
        "location",
        "availability",
        "verification",
        "ratings",
        "historical",
    }
    assert result["confidence_score"] <= 1.0
    assert WEIGHTS.skill == 40.0
