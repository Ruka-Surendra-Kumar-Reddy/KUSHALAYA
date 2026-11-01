"""AI visualization config — tiers, prompts, workflow map (spreadsheet-driven)."""

from __future__ import annotations

from copy import deepcopy

from app.livewell.ai_defaults import DEFAULT_AI_CONFIG

VALID_ROOM_TYPES = frozenset({"bathroom", "bedroom", "hallway", "kitchen", "entry"})
VALID_PACKAGE_LEVELS = frozenset({"essential", "comfort", "premium"})

DEFAULT_SETTINGS = dict(DEFAULT_AI_CONFIG.get("settings") or {})


def normalize_ai_config(raw: dict | None) -> dict:
    src = raw if isinstance(raw, dict) else {}
    defaults = deepcopy(DEFAULT_AI_CONFIG)

    tiers = []
    for i, row in enumerate(src.get("tiers") or defaults.get("tiers") or []):
        tid = str(row.get("id", "")).strip().lower()
        if not tid or tid not in VALID_PACKAGE_LEVELS:
            continue
        if row.get("active") is False:
            continue
        tiers.append(
            {
                "id": tid,
                "name": str(row.get("name", tid)).strip(),
                "description": str(row.get("description", "")).strip(),
                "sort_order": int(row.get("sort_order", i + 1)),
                "active": True,
            }
        )
    tiers.sort(key=lambda t: t["sort_order"])
    if not tiers:
        tiers = [t for t in defaults.get("tiers") or [] if t.get("active", True)]

    package_solutions = []
    for row in src.get("package_solutions") or []:
        tier = str(row.get("tier_id") or row.get("package_level") or "").strip().lower()
        room = str(row.get("room_type", "")).strip().lower()
        sid = str(row.get("solution_id") or "").strip()
        if not tier or not room or not sid:
            continue
        if tier not in VALID_PACKAGE_LEVELS or room not in VALID_ROOM_TYPES:
            continue
        package_solutions.append(
            {
                "tier_id": tier,
                "room_type": room,
                "solution_id": sid,
                "priority": int(row.get("priority", 0)),
                "active": row.get("active", True) is not False,
            }
        )

    vision_finding_map = []
    for row in src.get("vision_finding_map") or []:
        code = str(row.get("finding_code") or "").strip()
        sid = str(row.get("solution_id") or "").strip()
        if not code or not sid:
            continue
        vision_finding_map.append(
            {
                "finding_code": code,
                "room_type": str(row.get("room_type", "")).strip().lower() or None,
                "solution_id": sid,
                "min_confidence": int(row.get("min_confidence", 60)),
                "auto_apply_above": int(row.get("auto_apply_above", 85)),
                "active": row.get("active", True) is not False,
            }
        )

    prompt_templates = []
    for row in src.get("prompt_templates") or defaults.get("prompt_templates") or []:
        if row.get("active") is False:
            continue
        room = str(row.get("room_type", "")).strip().lower()
        level = str(row.get("package_level") or "").strip().lower()
        prompt = str(row.get("prompt_text") or "").strip()
        if not room or not level or not prompt:
            continue
        prompt_templates.append(
            {
                "id": str(row.get("id") or f"{room}_{level}_v1").strip(),
                "room_type": room,
                "package_level": level,
                "prompt_text": prompt,
                "negative_prompt": str(row.get("negative_prompt") or "").strip(),
                "version": int(row.get("version", 1)),
                "active": True,
            }
        )

    prompt_fragments = []
    for row in src.get("prompt_fragments") or []:
        sid = str(row.get("solution_id") or "").strip()
        frag = str(row.get("prompt_fragment") or row.get("fragment") or "").strip()
        if sid and frag:
            prompt_fragments.append({"solution_id": sid, "prompt_fragment": frag})

    workflow_map = []
    for row in src.get("workflow_map") or defaults.get("workflow_map") or []:
        if row.get("active") is False:
            continue
        room = str(row.get("room_type", "")).strip().lower()
        level = str(row.get("package_level") or "").strip().lower()
        wf = str(row.get("workflow_name") or "").strip()
        if not room or not level or not wf:
            continue
        workflow_map.append(
            {
                "room_type": room,
                "package_level": level,
                "workflow_name": wf,
                "model_name": str(row.get("model_name") or "flux-kontext").strip(),
                "draft_width": int(row.get("draft_width", 1024)),
                "draft_height": int(row.get("draft_height", 1024)),
                "active": True,
            }
        )

    settings = dict(DEFAULT_SETTINGS)
    incoming_settings = src.get("settings")
    if isinstance(incoming_settings, dict):
        for key, val in incoming_settings.items():
            settings[str(key)] = val

    return {
        "tiers": tiers,
        "package_solutions": package_solutions,
        "vision_finding_map": vision_finding_map,
        "prompt_templates": prompt_templates,
        "prompt_fragments": prompt_fragments,
        "workflow_map": workflow_map,
        "settings": settings,
    }


def ai_config_is_empty(data: dict) -> bool:
    """True when no tenant AI rows are stored (ignore normalize() factory fills)."""
    if not data:
        return True
    tiers = data.get("tiers") or []
    templates = data.get("prompt_templates") or []
    package_solutions = data.get("package_solutions") or []
    fragments = data.get("prompt_fragments") or []
    vision = data.get("vision_findings") or data.get("vision_finding_map") or []
    return not (tiers or templates or package_solutions or fragments or vision)


def get_ai_settings(config: dict) -> dict:
    return normalize_ai_config(config).get("settings") or dict(DEFAULT_SETTINGS)


def solutions_for_tier(config: dict, *, room_type: str, tier_id: str) -> list[str]:
    """Solution IDs allowed for a room + tier from spreadsheet config."""
    room = room_type.strip().lower()
    tier = tier_id.strip().lower()
    rows = normalize_ai_config(config).get("package_solutions") or []
    ids = [
        r["solution_id"]
        for r in rows
        if r.get("active", True)
        and r["room_type"] == room
        and r["tier_id"] == tier
    ]
    if ids:
        return ids
    # No spreadsheet rows — tier inherits all assessment solutions (Phase 1 fallback)
    return []


def filter_solutions_by_tier(
    config: dict,
    *,
    room_type: str,
    tier_id: str,
    assessment_solution_ids: list[str],
) -> list[str]:
    allowed = solutions_for_tier(config, room_type=room_type, tier_id=tier_id)
    if not allowed:
        # Progressive tier fallback: essential=first third, comfort=first two thirds, premium=all
        ordered = list(dict.fromkeys(assessment_solution_ids))
        n = len(ordered)
        if n == 0:
            return []
        if tier_id == "essential":
            return ordered[: max(1, n // 3)]
        if tier_id == "comfort":
            return ordered[: max(1, (2 * n) // 3)]
        return ordered
    allowed_set = set(allowed)
    return [sid for sid in assessment_solution_ids if sid in allowed_set]
