"""Family improvement plan built on the server.

The office wizard builds this plan in the browser (frontend lib/livewell/familyPublish.ts
→ buildImprovementPlan). "New assessment" and the caregiver app submit through
field_assessment.save_for_job, which had no plan, so families saw a score and
"No open improvement items". This mirrors the browser logic: every library solution
that fixes a question answered "unsafe" or "acceptable" becomes a plan item.
"""

from __future__ import annotations

from app.livewell.brand import with_brand
from app.livewell.scoring import effective_rubric, score_assessment
from app.livewell.solution_service import DEFAULT_SOLUTIONS, normalize_solutions
from app.livewell.stored_config import read_stored_config

FINDING_RATINGS = {"unsafe", "acceptable", "fail", "partial"}
PRIORITY_ORDER = ["critical", "high", "medium", "low"]
MAX_ITEMS = 12
# Same caps as frontend realisticProjection (improvement-plan.ts).
AREA_GAIN_CAP = 10
MAX_GAP_CLOSED = 0.8


def realistic_projection(current: int, entries: list[dict]) -> int:
    by_area: dict[str, list[int]] = {}
    for e in entries:
        area = e["solution"].get("section") or e["category"] or "Other"
        by_area.setdefault(area, []).append(max(0, int(e["solution"].get("scoreImprovement") or 0)))
    total = 0.0
    for gains in by_area.values():
        gains.sort(reverse=True)
        total += min(AREA_GAIN_CAP, sum(g * 0.5**i for i, g in enumerate(gains)))
    gap = max(0, 100 - current)
    return round(current + min(total, gap * MAX_GAP_CLOSED))


def build_family_plan(payload: dict, workflow_config: dict | None) -> dict | None:
    """The ``familyImprovementPlan`` block for a completed assessment payload, or None
    when it cannot be scored (no ratings)."""
    categories, _ = effective_rubric(workflow_config)
    result = score_assessment(payload, categories)
    if not result.get("rated_count"):
        return None
    current = int(result["independence_score"])
    ratings = payload.get("ratings") or {}
    category_of: dict[str, str] = {}
    for c in categories:
        title = str(c.get("title") or "").lstrip("0123456789. ")
        for i in c.get("items", []):
            if i.get("id") and ratings.get(i["id"]) in FINDING_RATINGS:
                category_of[i["id"]] = title

    stored = read_stored_config(workflow_config or {})["solutions"]
    # A team that never edited its library uses the shipped one (as the browser does).
    library = normalize_solutions(stored if stored.get("solutions") else DEFAULT_SOLUTIONS)
    entries = []
    for sol in library.get("solutions") or []:
        hits = [rid for rid in sol.get("rubricItemIds") or [] if rid in category_of]
        if hits:
            entries.append({"solution": sol, "category": category_of[hits[0]]})
    rank = {p: n for n, p in enumerate(PRIORITY_ORDER)}
    entries.sort(key=lambda e: (rank.get(e["solution"].get("priority"), 9),
                                -int(e["solution"].get("scoreImprovement") or 0)))

    items = []
    for e in entries[:MAX_ITEMS]:
        s = e["solution"]
        items.append({
            "id": str(s.get("id")),
            "title": s.get("name") or s.get("finding") or "Improvement",
            "priority": s.get("priority") or "medium",
            "why": s.get("riskDescription") or None,
            "actions": list(s.get("recommendedSolutions") or [])[:4],
            "score_gain": int(s.get("scoreImprovement") or 0),
            "status": "open",
            "domain": s.get("section") or None,
            "estimated_cost": (str(s.get("estimatedCost") or "").strip() or None),
        })
    costs = [i["estimated_cost"] for i in items if i["estimated_cost"]][:4]
    return {
        "current_score": current,
        "projected_score": realistic_projection(current, entries),
        "finding_count": len(category_of),
        "items": items,
        "estimated_cost_note": (
            with_brand(f"Indicative ranges from the plan: {' · '.join(costs)}. Final quote confirmed by LiveWell360.")
            if costs else None
        ),
    }
