"""Default SafeHome 360™ rubric — loaded from default_rubric.json."""

from __future__ import annotations

import json
from pathlib import Path

from app.livewell.rubric_service import normalize_rubric

_DATA_FILE = Path(__file__).resolve().parent / "default_rubric.json"


def _load_file_defaults() -> dict:
    with _DATA_FILE.open(encoding="utf-8") as f:
        return json.load(f)


DEFAULT_RUBRIC: dict = normalize_rubric(_load_file_defaults())
