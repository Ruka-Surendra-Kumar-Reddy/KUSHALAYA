"""Home safety assessment rubric — mirrors frontend/lib/livewell/assessment.ts."""

from __future__ import annotations

from typing import Literal

ItemRating = Literal["fail", "partial", "pass"] | None

SAFETY_CATEGORIES: list[dict] = [
    {
        "id": "bathroom",
        "title": "Bathroom Safety",
        "max_points": 25,
        "items": [
            {"id": "bathroom_grab_bars", "label": "Grab bars installed", "max_points": 5},
            {"id": "bathroom_anti_slip", "label": "Anti-slip flooring", "max_points": 5},
            {"id": "bathroom_shower", "label": "Shower accessibility", "max_points": 5},
            {"id": "bathroom_toilet", "label": "Toilet support", "max_points": 5},
            {"id": "bathroom_lighting", "label": "Adequate lighting", "max_points": 5},
        ],
    },
    {
        "id": "mobility",
        "title": "Mobility & Accessibility",
        "max_points": 20,
        "items": [
            {"id": "mobility_handrails", "label": "Handrails", "max_points": 5},
            {"id": "mobility_stairs", "label": "Stair safety", "max_points": 5},
            {"id": "mobility_walkways", "label": "Clear walkways", "max_points": 5},
            {"id": "mobility_threshold", "label": "Threshold safety", "max_points": 5},
        ],
    },
    {
        "id": "lighting",
        "title": "Lighting & Visibility",
        "max_points": 15,
        "items": [
            {"id": "lighting_hallway", "label": "Hallway lighting", "max_points": 5},
            {"id": "lighting_night", "label": "Night lighting", "max_points": 5},
            {"id": "lighting_motion", "label": "Motion lights", "max_points": 5},
        ],
    },
    {
        "id": "bedroom",
        "title": "Bedroom Safety",
        "max_points": 10,
        "items": [
            {"id": "bedroom_height", "label": "Bed height", "max_points": 4},
            {"id": "bedroom_rails", "label": "Bed rails", "max_points": 3},
            {"id": "bedroom_space", "label": "Walking space", "max_points": 3},
        ],
    },
    {
        "id": "emergency",
        "title": "Emergency Preparedness",
        "max_points": 10,
        "items": [
            {"id": "emergency_contacts", "label": "Emergency contacts", "max_points": 4},
            {"id": "emergency_medical", "label": "Medical information", "max_points": 3},
            {"id": "emergency_plan", "label": "Emergency response plan", "max_points": 3},
        ],
    },
    {
        "id": "smart",
        "title": "Smart Safety",
        "max_points": 10,
        "items": [
            {"id": "smart_doorbell", "label": "Video doorbell", "max_points": 3},
            {"id": "smart_sos", "label": "SOS system", "max_points": 3},
            {"id": "smart_motion", "label": "Motion sensors", "max_points": 2},
            {"id": "smart_family", "label": "Family notifications", "max_points": 2},
        ],
    },
    {
        "id": "general",
        "title": "General Safety",
        "max_points": 10,
        "items": [
            {"id": "general_clutter", "label": "Clutter free", "max_points": 4},
            {"id": "general_rugs", "label": "Loose rugs removed", "max_points": 3},
            {"id": "general_furniture", "label": "Furniture layout", "max_points": 3},
        ],
    },
]

TOTAL_MAX_POINTS = sum(c["max_points"] for c in SAFETY_CATEGORIES)


def item_points(rating: ItemRating, max_points: int) -> float:
    if rating == "pass":
        return float(max_points)
    if rating == "partial":
        return round(max_points * 0.5, 1)
    return 0.0


def total_score(ratings: dict[str, ItemRating]) -> float:
    total = 0.0
    for cat in SAFETY_CATEGORIES:
        for item in cat["items"]:
            total += item_points(ratings.get(item["id"]), item["max_points"])
    return total


def safety_grade(score_0_to_100: float) -> dict[str, str]:
    """SafeHome 360™ grade from normalized 0–100 score."""
    if score_0_to_100 >= 95:
        return {"grade": "Platinum", "label": "Platinum", "status": "platinum"}
    if score_0_to_100 >= 85:
        return {"grade": "Gold", "label": "Gold", "status": "gold"}
    if score_0_to_100 >= 75:
        return {"grade": "Silver", "label": "Silver", "status": "silver"}
    if score_0_to_100 >= 65:
        return {"grade": "Bronze", "label": "Bronze", "status": "bronze"}
    return {"grade": "Red", "label": "Immediate Action Required", "status": "red"}
