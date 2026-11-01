"""Shared parsers for LiveWell360 master workbook import formatting."""

from __future__ import annotations

import re
from typing import Any

_MONEY_NOISE = re.compile(r"(?i)₹|\$|\brs\.?\s*|\binr\b\s*")
_SCIENTIFIC = re.compile(r"^[+-]?\d+(?:\.\d+)?[eE][+-]?\d+$")
_TRAILING_DOT_ZERO = re.compile(r"^(\d+)\.0+$")


def noneish(text: str | None) -> bool:
    return (text or "").strip().lower() in ("", "none", "null", "n/a", "na", "-")


def parse_money_inr(text: Any) -> int | None:
    """Parse INR amounts from sheets: 3500, 3,500, ₹3,500, Rs 3500 → int.

    Returns None for blank/unparseable — never silently 0.
    """
    if text is None:
        return None
    if isinstance(text, bool):
        return None
    if isinstance(text, (int, float)):
        if isinstance(text, float) and (text != text):  # NaN
            return None
        return int(round(float(text)))

    s = str(text).strip()
    if noneish(s) or s.lower() in ("quote", "tbd", "na"):
        return None
    s = _MONEY_NOISE.sub("", s)
    s = s.replace(",", "").replace(" ", "").strip()
    # Leading dot left by partial currency strip (e.g. awkward cells)
    if s.startswith("."):
        s = s[1:]
    if not s:
        return None
    try:
        return int(round(float(s)))
    except (TypeError, ValueError):
        return None


def parse_percent(text: Any) -> float | None:
    """Parse 25, 25%, 0.25 (as percent points if > 1) — returns percent number (25.0)."""
    if text is None:
        return None
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return float(text)
    s = str(text).strip()
    if noneish(s):
        return None
    s = s.replace("%", "").replace(",", "").strip()
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def normalize_id_token(text: Any) -> str:
    """Clean Excel ID/code cells: 12345.0 → 12345; scientific ints within range → decimal."""
    if text is None:
        return ""
    if isinstance(text, bool):
        return "Yes" if text else "No"
    if isinstance(text, float) and text.is_integer():
        return str(int(text))
    if isinstance(text, int):
        return str(text)

    s = str(text).strip()
    if not s:
        return ""
    m = _TRAILING_DOT_ZERO.fullmatch(s)
    if m:
        return m.group(1)
    if _SCIENTIFIC.fullmatch(s):
        try:
            f = float(s)
            if f.is_integer() and abs(f) < 1e15:
                return str(int(f))
        except (TypeError, ValueError):
            pass
    return s


def normalize_category_prefix(text: str | None) -> str | None:
    if noneish(text):
        return None
    return str(text).strip().upper()
