"""The fixed list of hazards the AI room check may report, in plain words.

Every code links to one solution (→ products via catalog `solution_ids`) and, where one
exists, the assessment question it answers. The model is only ever offered these codes;
anything else it returns is dropped server-side. Tenants may add codes through
`home_safety_ai.vision_finding_map` (code → solution) or switch a built-in one off with
`active: false`; built-in links win for built-in codes.
"""

from __future__ import annotations

import hashlib
import json

from app.core.money import rupees_to_minor

# code, rooms ([] = any room), solution, rubric item, plain label, what to look for
BUILTIN_HAZARDS: tuple[dict, ...] = (
    {"code": "no_toilet_grab_bar", "rooms": ["bathroom"], "solution_id": "LW-HS-BTH-001",
     "rubric_item_id": "home_safety_toilet_grab_bar_installed",
     "label": "No grab bar next to the toilet",
     "look_for": "toilet with no fixed grab bar or support frame within reach"},
    {"code": "toilet_too_low", "rooms": ["bathroom"], "solution_id": "LW-HS-BTH-001",
     "rubric_item_id": "home_safety_toilet_height_appropriate",
     "label": "Toilet seat is low and hard to stand up from",
     "look_for": "low western toilet or Indian-style squat toilet with no raised seat"},
    {"code": "no_shower_grab_bar", "rooms": ["bathroom"], "solution_id": "LW-HS-BTH-002",
     "rubric_item_id": "home_safety_shower_grab_bar_installed",
     "label": "Nothing to hold in the shower area",
     "look_for": "shower or bathing area with no grab bar on the wall"},
    {"code": "slippery_bathroom_floor", "rooms": ["bathroom"], "solution_id": "LW-HS-BTH-004",
     "rubric_item_id": "home_safety_anti_slip_flooring",
     "label": "Slippery bathroom floor",
     "look_for": "glossy or wet tiles with no anti-slip strips or mat"},
    {"code": "no_shower_chair", "rooms": ["bathroom"], "solution_id": "LW-HS-BTH-003",
     "rubric_item_id": "home_safety_shower_chair_available",
     "label": "No shower chair or stool to sit while bathing",
     "look_for": "bathing area with no stable seat"},
    {"code": "dark_bathroom", "rooms": ["bathroom"], "solution_id": "LW-HS-BED-002",
     "rubric_item_id": None,
     "label": "Bathroom is poorly lit",
     "look_for": "dim bathroom, no light near the toilet or shower"},
    {"code": "no_entrance_handrail", "rooms": ["entry"], "solution_id": "LW-HS-ENT-002",
     "rubric_item_id": "home_safety_entrance_railing_if_needed",
     "label": "Steps at the entrance with no handrail",
     "look_for": "entrance steps without a rail to hold"},
    {"code": "poor_entrance_lighting", "rooms": ["entry"], "solution_id": "LW-HS-ENT-003",
     "rubric_item_id": "home_safety_adequate_entry_lighting",
     "label": "Entrance is poorly lit",
     "look_for": "dark doorway, porch or gate area"},
    {"code": "uneven_walkway", "rooms": ["entry", "hallway"], "solution_id": "LW-HS-ENT-001",
     "rubric_item_id": "home_safety_pathway_level_and_clear",
     "label": "Uneven or broken path to walk on",
     "look_for": "broken tiles, level changes, cracks on the walking path"},
    {"code": "step_at_entrance", "rooms": ["entry"], "solution_id": "LW-HS-ENT-004",
     "rubric_item_id": "home_safety_zero_step_or_ramped_main_entry",
     "label": "Raised step or threshold at the door",
     "look_for": "high door threshold or step with no ramp"},
    {"code": "trip_hazard_clutter", "rooms": [], "solution_id": "LW-HS-LIV-001",
     "rubric_item_id": "home_safety_hallways_free_of_trip_hazards",
     "label": "Clutter or objects on the floor to trip over",
     "look_for": "items, footwear, boxes or cables lying in the walking path"},
    {"code": "loose_rug", "rooms": [], "solution_id": "LW-HS-LIV-001",
     "rubric_item_id": "home_safety_loose_rugs_secured_or_removed",
     "label": "Loose rug or mat that can slip",
     "look_for": "rug, doormat or carpet edge not fixed to the floor"},
    {"code": "dark_hallway", "rooms": ["hallway", "bedroom"], "solution_id": "LW-HS-BED-002",
     "rubric_item_id": "home_safety_bedroom_night_lighting",
     "label": "Dark route at night (no night light)",
     "look_for": "passage or bedroom with no night light or switch near the bed"},
    {"code": "no_bed_rail", "rooms": ["bedroom"], "solution_id": "LW-HS-BED-001",
     "rubric_item_id": "home_safety_bed_transfer_support",
     "label": "Nothing to hold when getting in and out of bed",
     "look_for": "bed with no rail or support; very low or very high bed"},
    {"code": "stairs_no_handrail", "rooms": ["hallway", "entry"], "solution_id": "LW-HS-STA-001",
     "rubric_item_id": "mobility_stairs_manageable_or_alternative_exists",
     "label": "Stairs without a handrail",
     "look_for": "staircase with no rail on at least one side"},
    {"code": "gas_stove_risk", "rooms": ["kitchen"], "solution_id": "LW-HS-KIT-001",
     "rubric_item_id": "home_safety_stove_gas_safety_controls",
     "label": "Gas stove or cylinder with no safety device",
     "look_for": "gas stove or cylinder with no leak detector or extinguisher nearby"},
    {"code": "loose_wires", "rooms": [], "solution_id": "LW-HS-LIV-004",
     "rubric_item_id": "home_condition_electrical_outlets_wiring_safe",
     "label": "Loose wires or overloaded sockets",
     "look_for": "exposed wiring, extension boards with many plugs, cables across the floor"},
    {"code": "sharp_glass_table", "rooms": ["living", "bedroom"], "solution_id": "LW-HS-LIV-001",
     "rubric_item_id": None,
     "label": "Glass or sharp-edged table in the way",
     "look_for": "glass-top or sharp-cornered table near where the person walks"},
)

SEVERITY_BY_PRIORITY = {"critical": "urgent", "high": "soon", "medium": "watch", "low": "watch"}
SEVERITY_LABELS = {"urgent": "Urgent", "soon": "Soon", "watch": "Watch"}
SEVERITY_ORDER = {"urgent": 0, "soon": 1, "watch": 2}

ROOM_LABELS = {
    "bathroom": "Bathroom",
    "bedroom": "Bedroom",
    "hallway": "Hallway",
    "kitchen": "Kitchen",
    "entry": "Entrance",
    "living": "Living room",
}


def room_label(room: str | None) -> str:
    if not room:
        return "Room"
    return ROOM_LABELS.get(room.strip().lower(), room.strip().title())


def _norm_room(room: str | None) -> str | None:
    r = (room or "").strip().lower()
    if r in ("entrance", "front_door", "door"):
        return "entry"
    if r in ("living_room", "hall", "lounge"):
        return "living"
    return r or None


def build_catalog(
    *,
    vision_finding_map: list[dict] | None,
    solutions: list[dict],
    rubric_labels: dict[str, str],
) -> dict[str, dict]:
    """code -> hazard definition (label, rooms, solution, severity, rubric question)."""
    by_solution = {str(s.get("id")): s for s in solutions if s.get("id")}
    disabled: set[str] = set()
    extra: list[dict] = []
    builtin_codes = {h["code"] for h in BUILTIN_HAZARDS}
    for row in vision_finding_map or []:
        code = str(row.get("finding_code") or "").strip()
        if not code:
            continue
        if row.get("active") is False:
            disabled.add(code)
            continue
        if code in builtin_codes:
            continue
        sid = str(row.get("solution_id") or "").strip()
        sol = by_solution.get(sid) or {}
        rubric_ids = sol.get("rubricItemIds") or []
        extra.append(
            {
                "code": code,
                "rooms": [r for r in [_norm_room(row.get("room_type"))] if r],
                "solution_id": sid,
                "rubric_item_id": rubric_ids[0] if rubric_ids else None,
                "label": str(sol.get("finding") or code.replace("_", " ")).strip(),
                "look_for": str(sol.get("finding") or "").strip(),
            }
        )

    out: dict[str, dict] = {}
    for h in list(BUILTIN_HAZARDS) + extra:
        if h["code"] in disabled:
            continue
        sol = by_solution.get(h["solution_id"]) or {}
        priority = str(sol.get("priority") or "medium").strip().lower()
        severity = SEVERITY_BY_PRIORITY.get(priority, "watch")
        rubric_id = h.get("rubric_item_id")
        out[h["code"]] = {
            **h,
            "solution_name": sol.get("name") or sol.get("finding") or h["solution_id"],
            "priority": priority,
            "severity": severity,
            "severity_label": SEVERITY_LABELS[severity],
            "rubric_item_id": rubric_id,
            "question": rubric_labels.get(rubric_id or "", None),
        }
    return out


def codes_for_room(catalog: dict[str, dict], room: str | None) -> list[str]:
    r = _norm_room(room)
    if not r:
        return list(catalog)
    return [c for c, h in catalog.items() if not h["rooms"] or r in h["rooms"]]


def catalog_hash(codes: list[str]) -> str:
    return hashlib.sha256(json.dumps(sorted(codes)).encode()).hexdigest()[:16]


def products_for_solution(catalog_products: list[dict], solution_id: str, *, gst_bp: int = 1800) -> list[dict]:
    """Catalog products whose `solution_ids` include this solution, priced incl. GST (paise)."""
    out: list[dict] = []
    for p in catalog_products or []:
        if solution_id not in (p.get("solution_ids") or []):
            continue
        code = p.get("product_code")
        if not code:
            continue
        price_inr = p.get("price_inr")
        try:
            base_paise = rupees_to_minor(price_inr) if price_inr not in (None, "") else 0
        except (TypeError, ValueError, ArithmeticError):
            base_paise = 0
        out.append(
            {
                "product_code": code,
                "name": p.get("name") or code,
                "category": p.get("category") or "",
                "price_paise": base_paise,
                "price_with_gst_paise": base_paise + base_paise * gst_bp // 10000 if base_paise else None,
                "price_label": p.get("price_label") or "Quote",
                "sort_order": int(p.get("sort_order") or 0),
            }
        )
    out.sort(key=lambda r: (r["sort_order"], r["name"]))
    return out
