"""AI room hazard check — Gemini call with a strict JSON schema, plus image clean-up.

Only the cleaned image and our allowed hazard list leave the server: no names, no
address, no health data. EXIF (incl. GPS) is removed by re-encoding the pixels.
"""

from __future__ import annotations

import base64
import io
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_SIDE = 1600
_logged_missing_models: set[str] = set()
_working_model: str | None = None


class HazardProviderError(RuntimeError):
    """A failed call the user can retry (message is safe to show)."""


@dataclass
class HazardDetection:
    code: str
    confidence: int  # 0–100
    box: list[float] | None  # normalised [x, y, w, h], 0–1, or None
    evidence: str | None = None


@dataclass
class HazardResult:
    provider: str
    model: str
    hazards: list[HazardDetection] = field(default_factory=list)
    notes: str | None = None
    rejected_codes: list[str] = field(default_factory=list)


class HazardProvider(Protocol):
    def name(self) -> str: ...
    def model_version(self) -> str: ...
    def is_configured(self) -> bool: ...
    def detect(self, image_jpeg: bytes, hazards: list[dict]) -> HazardResult: ...


# --- image clean-up ------------------------------------------------------------


def strip_image_metadata(raw: bytes, *, max_side: int = MAX_SIDE) -> bytes:
    """Re-encode as JPEG with no EXIF/GPS/ICC metadata.

    EXIF orientation is applied to the pixels first, so boxes the model returns line up
    with the photo as browsers show it. Large photos are scaled down (cost, speed).
    """
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(raw)) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        if max(im.size) > max_side:
            im.thumbnail((max_side, max_side))
        clean = Image.new(im.mode, im.size)
        clean.paste(im)
        out = io.BytesIO()
        clean.save(out, format="JPEG", quality=85)
        return out.getvalue()


# --- response validation -------------------------------------------------------


def box_from_yxyx(value: Any) -> list[float] | None:
    """Gemini box_2d [ymin, xmin, ymax, xmax] on a 0–1000 grid -> [x, y, w, h] in 0–1.

    Returns None (no box drawn) for anything malformed, empty or covering the whole frame.
    """
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        ymin, xmin, ymax, xmax = (float(v) for v in value)
    except (TypeError, ValueError):
        return None
    if any(v != v for v in (ymin, xmin, ymax, xmax)):  # NaN
        return None
    if min(ymin, xmin, ymax, xmax) < -5 or max(ymin, xmin, ymax, xmax) > 1005:
        return None
    ymin, xmin = max(0.0, ymin), max(0.0, xmin)
    ymax, xmax = min(1000.0, ymax), min(1000.0, xmax)
    w, h = (xmax - xmin) / 1000.0, (ymax - ymin) / 1000.0
    if w <= 0.01 or h <= 0.01:
        return None
    if w * h >= 0.98:
        return None
    return [round(xmin / 1000.0, 4), round(ymin / 1000.0, 4), round(w, 4), round(h, 4)]


def parse_hazard_payload(parsed: Any, allowed_codes: list[str]) -> tuple[list[HazardDetection], list[str], str | None]:
    """Validate the model's JSON. Unknown codes are dropped and reported back."""
    if not isinstance(parsed, dict):
        raise HazardProviderError("The AI reply was not in the expected format.")
    rows = parsed.get("hazards")
    if rows is None:
        rows = []
    if not isinstance(rows, list):
        raise HazardProviderError("The AI reply was not in the expected format.")
    allowed = set(allowed_codes)
    best: dict[str, HazardDetection] = {}
    rejected: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or "").strip()
        if code not in allowed:
            if code:
                rejected.append(code[:64])
            continue
        try:
            conf = float(row.get("confidence"))
        except (TypeError, ValueError):
            continue
        if conf <= 1.0:
            conf *= 100.0
        conf_i = int(round(max(0.0, min(100.0, conf))))
        evidence = str(row.get("evidence") or "").strip()[:240] or None
        det = HazardDetection(code=code, confidence=conf_i, box=box_from_yxyx(row.get("box_2d")), evidence=evidence)
        prev = best.get(code)
        if prev is None or det.confidence > prev.confidence:
            best[code] = det
    notes = str(parsed.get("notes") or "").strip()[:500] or None
    return sorted(best.values(), key=lambda d: -d.confidence), rejected, notes


def build_prompt(hazards: list[dict]) -> str:
    lines = [f'- "{h["code"]}": {h["label"]} (look for: {h.get("look_for") or h["label"]})' for h in hazards]
    return (
        "You check one photo of a room in an older person's home in India for fall and "
        "safety hazards.\n"
        "Report ONLY hazards from this list, using the code exactly:\n"
        + "\n".join(lines)
        + "\n\nRules:\n"
        "- Only report what is clearly visible in the photo. Absence you cannot see is not a hazard.\n"
        "- confidence: 0-100, how sure you are this hazard is present in the photo.\n"
        "- box_2d: [ymin, xmin, ymax, xmax] on a 0-1000 grid around the hazard. "
        "Leave it out if the hazard has no single place in the photo.\n"
        "- evidence: under 15 words, plain English, what you see.\n"
        "- A hazard not in the list goes in notes, never as a new code.\n"
        "- Empty hazards list if the photo shows none.\n"
    )


def response_schema(codes: list[str]) -> dict:
    return {
        "type": "OBJECT",
        "properties": {
            "hazards": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "code": {"type": "STRING", "enum": codes},
                        "confidence": {"type": "NUMBER"},
                        "box_2d": {"type": "ARRAY", "items": {"type": "NUMBER"}},
                        "evidence": {"type": "STRING"},
                    },
                    "required": ["code", "confidence"],
                },
            },
            "notes": {"type": "STRING"},
        },
        "required": ["hazards"],
    }


def _extract_text(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
    text = "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict)).strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


# --- providers -----------------------------------------------------------------


def model_candidates() -> list[str]:
    primary = (settings.AI_VISION_MODEL or "gemini-3.5-flash").strip()
    fallbacks = [m.strip() for m in (settings.AI_VISION_MODEL_FALLBACKS or "").split(",") if m.strip()]
    ordered = [_working_model] if _working_model else []
    return list(dict.fromkeys([m for m in ordered + [primary] + fallbacks if m]))


class GeminiHazardProvider:
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = (api_key if api_key is not None else settings.GEMINI_API_KEY or "").strip()
        self._model = model_candidates()[0]

    def name(self) -> str:
        return "gemini"

    def model_version(self) -> str:
        return self._model

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def detect(self, image_jpeg: bytes, hazards: list[dict]) -> HazardResult:
        global _working_model
        if not self.is_configured():
            raise HazardProviderError("AI checks are not switched on (no Gemini key on the server).")
        codes = [h["code"] for h in hazards]
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": build_prompt(hazards)},
                        {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(image_jpeg).decode("ascii")}},
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
                "responseSchema": response_schema(codes),
            },
        }
        last_error = "The AI service did not answer."
        for model in model_candidates():
            try:
                with httpx.Client(timeout=60.0) as client:
                    # Key goes in a header, never in the URL (URLs end up in logs).
                    resp = client.post(
                        GEMINI_URL.format(model=model),
                        headers={"x-goog-api-key": self._api_key},
                        json=body,
                    )
            except httpx.TimeoutException as exc:
                raise HazardProviderError("The AI service took too long. Please try again.") from exc
            except httpx.HTTPError as exc:
                raise HazardProviderError("Could not reach the AI service. Please try again.") from exc
            if resp.status_code == 404:
                if model not in _logged_missing_models:
                    _logged_missing_models.add(model)
                    logger.warning("Gemini model %s not available (404); trying the next fallback", model)
                last_error = "The configured AI model is not available."
                continue
            if resp.status_code == 429:
                raise HazardProviderError("The AI service is busy right now. Please try again in a minute.")
            if resp.status_code >= 400:
                logger.warning("Gemini hazard check failed HTTP %s", resp.status_code)
                raise HazardProviderError(f"The AI service returned an error ({resp.status_code}).")
            self._model = model
            _working_model = model
            text = _extract_text(resp.json())
            try:
                parsed = json.loads(text) if text else {"hazards": []}
            except json.JSONDecodeError as exc:
                raise HazardProviderError("The AI reply was not in the expected format.") from exc
            found, rejected, notes = parse_hazard_payload(parsed, codes)
            return HazardResult(provider="gemini", model=model, hazards=found, notes=notes, rejected_codes=rejected)
        raise HazardProviderError(last_error)


_provider_override: HazardProvider | None = None


def set_hazard_provider_for_tests(provider: HazardProvider | None) -> None:
    global _provider_override
    _provider_override = provider


def get_hazard_provider() -> HazardProvider:
    if _provider_override is not None:
        return _provider_override
    return GeminiHazardProvider()
