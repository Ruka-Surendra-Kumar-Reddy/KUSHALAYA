"""Default Safe Home product catalog — mirrored from Kushalaya_Configuration.xlsx.

Source of truth: ``data/Kushalaya_Configuration.xlsx`` (sheets 05–06, 10–11).
Regenerate this file with:

  python backend/scripts/sync_catalog_defaults_from_workbook.py

Do not hand-edit product/package rows here.
"""

from __future__ import annotations

import json
from pathlib import Path

_DATA_FILE = Path(__file__).resolve().parent / "default_catalog.json"


def _load_file_defaults() -> dict:
    with _DATA_FILE.open(encoding="utf-8") as f:
        return json.load(f)


DEFAULT_CATALOG: dict = _load_file_defaults()
