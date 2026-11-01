"""Legacy flat LW-* solution IDs → Library v1 LW-CAT-SUB-nnn IDs.

Applied when loading catalogs / linking products so older tenant data keeps working.
"""

from __future__ import annotations

import json
from pathlib import Path

LEGACY_TO_V1: dict[str, str] = {}

_DATA_FILE = Path(__file__).resolve().parent / "default_solutions.json"
_FACTORY: dict[str, str] | None = None


def _aliases_of(solutions: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for sol in solutions or []:
        new_id = str(sol.get("id") or "").strip()
        if not new_id:
            continue
        for legacy in sol.get("legacyIds") or []:
            lid = str(legacy).strip()
            if lid and lid != new_id:
                out[lid] = new_id
    return out


def _factory_aliases() -> dict[str, str]:
    """legacyIds from the shipped solution library — always known, whatever was loaded last."""
    global _FACTORY
    if _FACTORY is None:
        _FACTORY = {}
        if _DATA_FILE.is_file():
            with _DATA_FILE.open(encoding="utf-8") as f:
                _FACTORY = _aliases_of(json.load(f).get("solutions") or [])
    return _FACTORY


def reload_aliases_from_solutions(solutions: list[dict]) -> None:
    """Factory legacy ids plus the given library's own legacyIds (the given library wins).

    Rebuilt from scratch each time, so a small library (a test, a partial workbook) can
    never drop the factory map and make results depend on what was loaded before.
    """
    merged = dict(_factory_aliases())
    merged.update(_aliases_of(solutions))
    LEGACY_TO_V1.clear()
    LEGACY_TO_V1.update(merged)


def _ensure_loaded() -> None:
    if not LEGACY_TO_V1:
        LEGACY_TO_V1.update(_factory_aliases())


def resolve_solution_id(solution_id: str) -> str:
    _ensure_loaded()
    sid = str(solution_id or "").strip()
    return LEGACY_TO_V1.get(sid, sid)


def remap_solution_ids(ids: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in ids or []:
        sid = resolve_solution_id(str(raw))
        if sid and sid not in seen:
            seen.add(sid)
            out.append(sid)
    return out
