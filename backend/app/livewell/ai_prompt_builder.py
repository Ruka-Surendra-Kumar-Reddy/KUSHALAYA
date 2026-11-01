"""Build RunPod-ready prompts from tenant AI config + approved solutions."""

from __future__ import annotations

from app.livewell.ai_config_service import (
    filter_solutions_by_tier,
    get_ai_settings,
    normalize_ai_config,
)


def _fragment_for_solution(config: dict, solution_id: str, solutions_lib: dict) -> str:
    fragments = normalize_ai_config(config).get("prompt_fragments") or []
    for row in fragments:
        if row.get("solution_id") == solution_id and row.get("prompt_fragment"):
            return str(row["prompt_fragment"]).strip()

    for sol in solutions_lib.get("solutions") or []:
        if sol.get("id") == solution_id:
            finding = str(sol.get("finding") or "").strip()
            recs = sol.get("recommendedSolutions") or []
            if recs:
                return f"{finding}: {', '.join(recs)}" if finding else ", ".join(recs)
            if finding:
                return finding
    return solution_id


def build_approved_modifications_text(
    config: dict,
    *,
    room_type: str,
    tier_id: str,
    approved_solution_ids: list[str],
    solutions_lib: dict,
) -> str:
    filtered = filter_solutions_by_tier(
        config,
        room_type=room_type,
        tier_id=tier_id,
        assessment_solution_ids=approved_solution_ids,
    )
    lines = [
        f"- {_fragment_for_solution(config, sid, solutions_lib)}"
        for sid in filtered
    ]
    return "\n".join(lines) if lines else "- General senior safety improvements per assessment."


def select_prompt_template(config: dict, *, room_type: str, package_level: str) -> dict | None:
    room = room_type.strip().lower()
    level = package_level.strip().lower()
    templates = normalize_ai_config(config).get("prompt_templates") or []
    for tpl in templates:
        if tpl.get("room_type") == room and tpl.get("package_level") == level:
            return tpl
    return None


def select_workflow_map(config: dict, *, room_type: str, package_level: str) -> dict | None:
    room = room_type.strip().lower()
    level = package_level.strip().lower()
    for row in normalize_ai_config(config).get("workflow_map") or []:
        if row.get("room_type") == room and row.get("package_level") == level:
            return row
    return None


def build_prompt_bundle(
    config: dict,
    *,
    room_type: str,
    package_level: str,
    approved_solution_ids: list[str],
    solutions_lib: dict,
) -> dict:
    """Return prompt_text, negative_prompt, workflow_name, model_name, dimensions."""
    tpl = select_prompt_template(config, room_type=room_type, package_level=package_level)
    wf = select_workflow_map(config, room_type=room_type, package_level=package_level)
    mods = build_approved_modifications_text(
        config,
        room_type=room_type,
        tier_id=package_level,
        approved_solution_ids=approved_solution_ids,
        solutions_lib=solutions_lib,
    )

    if not tpl:
        raise ValueError(
            f"No active prompt template for room_type={room_type} package_level={package_level}"
        )

    prompt_text = str(tpl.get("prompt_text") or "").replace("{approved_modifications}", mods)
    negative_prompt = str(tpl.get("negative_prompt") or "").strip()
    workflow_name = str((wf or {}).get("workflow_name") or tpl.get("id") or "").strip()
    model_name = str((wf or {}).get("model_name") or "flux-kontext").strip()
    width = int((wf or {}).get("draft_width") or 1024)
    height = int((wf or {}).get("draft_height") or 1024)

    return {
        "prompt_text": prompt_text,
        "negative_prompt_text": negative_prompt,
        "workflow_name": workflow_name,
        "workflow_version": int(tpl.get("version") or 1),
        "model_name": model_name,
        "draft_width": width,
        "draft_height": height,
        "settings": get_ai_settings(config),
    }


# --- AI room preview (FLUX Kontext edit) -------------------------------------------

# Product keyword → explicit placement used in the item-by-item prompt.
PLACEMENT_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("l-shaped grab", "l shaped grab"),
     "mount a stainless-steel L-shaped grab bar on the wall right beside the toilet or shower, at hand height"),
    (("foldable grab", "fold-up", "fold up"),
     "mount a stainless-steel fold-up grab rail on the wall next to the toilet, folded down, at hand height"),
    (("floor supported grab", "toilet safety frame", "toilet frame"),
     "place a free-standing metal safety frame with armrests around the toilet"),
    (("grab bar", "grab rail"),
     "mount a straight stainless-steel grab bar horizontally on the wall beside the toilet or in the shower, at hand height"),
    (("anti-slip strip", "anti slip strip", "anti-slip tape"),
     "apply clearly visible parallel anti-slip safety strips across the floor tiles in the wet area"),
    (("anti-slip floor", "anti-slip coating", "floor coating"),
     "give the existing floor tiles a subtle matte anti-slip finish without changing their colour or pattern"),
    (("bath mat", "anti-slip mat", "rubber mat"),
     "lay a rubber anti-slip mat on the floor in front of the shower"),
    (("shower chair", "shower seat", "bath seat"),
     "place a white shower chair with a backrest inside the shower area"),
    (("transfer bench",), "place a bath transfer bench across the shower edge"),
    (("raised toilet", "toilet seat"), "fit a raised toilet seat with armrests on the existing toilet"),
    (("handheld shower", "hand shower"), "add a handheld shower head on a slide bar mounted on the shower wall"),
    (("thermostatic", "mixer", "temp limit"), "replace the shower mixer with a thermostatic mixer valve"),
    (("night light", "motion sensor light", "motion light"),
     "add a small plug-in motion-sensor night light low on the wall near the floor"),
    (("led strip",), "add a warm LED strip light along the bottom of the wall at floor level"),
    (("bed rail",), "attach a metal bed rail to the side of the existing bed"),
    (("bed riser",), "raise the existing bed slightly on bed risers under its legs"),
    (("fall mat",), "lay a padded fall mat on the floor beside the bed"),
    (("handrail", "railing"), "mount a sturdy handrail on the wall along the stairs or corridor at hand height"),
    (("ramp",), "place a low threshold ramp across the door threshold"),
    (("rug pad",), "put a non-slip pad under the existing rug so it lies flat"),
    (("sos", "pull cord", "emergency button", "alert"),
     "mount a small red emergency SOS button or pull cord on the wall within reach"),
]


def placement_for(name: str) -> str:
    low = (name or "").lower()
    for keys, hint in PLACEMENT_HINTS:
        if any(k in low for k in keys):
            return hint
    return f"add a {name} in the most natural, realistic position for it"


TIER_STYLE = {
    "essential": "simple, functional standard fittings",
    "comfort": "good-quality fittings that match the room's finishes",
    "premium": "premium fittings in brushed stainless steel that match the room's finishes",
}


def build_room_preview_prompt(
    *,
    room_type: str,
    package_level: str,
    product_names: list[str],
    strict: bool = False,
    missing: list[str] | None = None,
    unwanted: list[str] | None = None,
) -> str:
    """Kontext edit prompt: keep the room identical, add only the listed products.

    `strict` (the one automatic retry) lists every item with an explicit placement and
    repeats the preservation rules; `missing` names the items the check could not see.
    Only product names go in — never client names or health details.
    """
    room = (room_type or "room").replace("_", " ").strip().lower() or "room"
    style = TIER_STYLE.get((package_level or "").strip().lower(), TIER_STYLE["comfort"])
    names = [n for n in product_names if n]
    keep = (
        "Keep everything else exactly as in the original photo: same camera angle, framing and perspective; "
        "same walls, wall colour and tiles; keep the original floor tile colour and pattern; same ceiling, "
        "doors, windows, fixtures and furniture in the same positions; same lighting and shadows. "
        "Do not remove, move, restyle or recolour anything already in the room. Do not add any other objects. "
        "Photorealistic, same image quality."
    )
    if not strict:
        lines = "\n".join(f"- {placement_for(n)} ({n})" for n in names)
        return (
            f"Edit this exact photo of a {room}. Add only these home-safety products, {style}, "
            f"each clearly visible:\n{lines}\n\n{keep}"
        )
    focus = missing or names
    steps = "\n".join(f"{i}. {placement_for(n)}. This item MUST be clearly visible: {n}." for i, n in enumerate(names, start=1))
    miss = (
        "The previous attempt did not show: " + ", ".join(focus) + ". Make sure these are clearly visible this time.\n"
        if missing
        else ""
    )
    undo = (
        "The previous attempt also wrongly changed the room (" + "; ".join(unwanted) + "). Do not do that: "
        "keep exactly the same fixtures and furniture, the same number of each, in the same places.\n"
        if unwanted
        else ""
    )
    return (
        f"Edit this exact photo of a {room}. Make these changes one by one, {style}:\n{steps}\n\n"
        f"{miss}{undo}IMPORTANT: change nothing else. {keep}"
    )
