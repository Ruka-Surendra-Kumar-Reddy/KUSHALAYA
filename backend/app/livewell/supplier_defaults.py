"""Default SafeHome 360™ supplier directory."""

from __future__ import annotations

import json
from pathlib import Path

_DATA_FILE = Path(__file__).resolve().parent / "default_suppliers.json"


def _load() -> dict:
    with _DATA_FILE.open(encoding="utf-8") as f:
        return json.load(f)


DEFAULT_SUPPLIERS: dict = _load()
