"""Default AI visualization config — loaded from default_ai_config.json."""

from __future__ import annotations

import json
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parent / "default_ai_config.json"


def load_default_ai_config() -> dict:
    with _DEFAULT_PATH.open(encoding="utf-8") as f:
        return json.load(f)


DEFAULT_AI_CONFIG = load_default_ai_config()
