"""Public-facing product brand (display name only).

Internal vertical id stays LIVEWELL360. Override with BRAND_NAME in env.
"""

from __future__ import annotations

from app.core.config import settings

DEFAULT_BRAND_NAME = "KushAlaya"
BRAND_TOKEN = "LiveWell360"


def brand_name() -> str:
    name = (settings.BRAND_NAME or "").strip()
    return name or DEFAULT_BRAND_NAME


def with_brand(text: str) -> str:
    name = brand_name()
    out = text
    if name != f"{BRAND_TOKEN}™":
        out = out.replace(f"{BRAND_TOKEN}™", name)
    if name != BRAND_TOKEN:
        out = out.replace(BRAND_TOKEN, name)
    return out


def safety_score_name() -> str:
    """Customer-facing name of the 0-100 home score (was "Independence Score")."""
    return f"{brand_name()} Safety Score"
