"""Product-presence QA for AI room previews.

After a render, ask Gemini (same REST API as ai_vision_provider, separate helper so the
hazard-check code is untouched) whether each requested product is visible in the
"after" image, with a bounding box, and — given the original photo too — whether
anything else in the room was added, removed, duplicated or moved (e.g. a second
toilet). Missing items or other changes trigger one stronger retry and block approval;
boxes place the numbered markers on the image.

Only the generated image and product names are sent — no client names or health data.
"""

from __future__ import annotations

import base64
import json
import logging

log = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
PRESENT_MIN_CONFIDENCE = 0.5


def _mime(data: bytes) -> str:
    return "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"


MAX_CHANGES = 5


def _prompt(names: list[str], with_before: bool = False) -> str:
    listing = "\n".join(f"{i}. {n}" for i, n in enumerate(names, start=1))
    if with_before:
        return (
            "Image 1 is the original photo of a room. Image 2 is the same room after an AI edit that "
            "was only allowed to add the numbered safety products below.\n"
            "1) For EACH numbered product, decide strictly whether that specific product is clearly "
            "visible in image 2 (a similar but different object does not count, e.g. a toilet-paper "
            "holder is not a grab bar).\n"
            "2) List every OTHER difference between the images that is not one of the products: any "
            "fixture, furniture or object added, removed, duplicated or moved (for example a second "
            "toilet, a missing sink, a moved door or window). Ignore small changes in lighting, colour, "
            "sharpness or camera angle. Use an empty list if there are none.\n"
            f"{listing}\n\n"
            "Reply with JSON only: {\"items\": [{\"n\": <number>, \"product\": <name>, \"present\": true|false, "
            "\"confidence\": 0..1, \"box_2d\": [ymin, xmin, ymax, xmax] in image 2 on a 0-1000 scale or null}], "
            "\"changes\": [<short description of each other difference>]}"
        )
    return (
        "You are checking an illustration of a home after safety products were added.\n"
        "For EACH numbered product below, decide strictly whether that specific product is clearly "
        "visible in the image (a similar but different object does not count, e.g. a toilet-paper "
        "holder is not a grab bar).\n"
        f"{listing}\n\n"
        "Reply with JSON only: {\"items\": [{\"n\": <number>, \"product\": <name>, \"present\": true|false, "
        "\"confidence\": 0..1, \"box_2d\": [ymin, xmin, ymax, xmax] on a 0-1000 scale or null}]}"
    )


def _call_gemini(image: bytes, names: list[str], before: bytes | None = None) -> dict | None:
    """Raw Gemini call; returns the parsed JSON object or None. Patched in tests."""
    import httpx

    from app.core.config import settings

    key = (settings.GEMINI_API_KEY or "").strip()
    if not key:
        return None
    models = [settings.AI_VISION_MODEL] + [
        m.strip() for m in (settings.AI_VISION_MODEL_FALLBACKS or "").split(",") if m.strip()
    ]
    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": _prompt(names, with_before=bool(before))},
                    *(
                        [{"inline_data": {"mime_type": _mime(before), "data": base64.b64encode(before).decode("ascii")}}]
                        if before
                        else []
                    ),
                    {"inline_data": {"mime_type": _mime(image), "data": base64.b64encode(image).decode("ascii")}},
                ],
            }
        ],
        "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"},
    }
    for model in dict.fromkeys(models):
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(GEMINI_URL.format(model=model), params={"key": key}, json=body)
        except Exception as exc:  # network
            log.warning("preview QA request failed: %s", type(exc).__name__)
            return None
        if resp.status_code == 404:
            continue
        if resp.status_code >= 400:
            log.warning("preview QA HTTP %s", resp.status_code)
            return None
        try:
            payload = resp.json()
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            data = json.loads(text)
            if isinstance(data, list):
                data = {"items": data}
            data["_model"] = model
            return data
        except Exception:
            return None
    return None


def _box(raw) -> dict | None:
    """Gemini [ymin, xmin, ymax, xmax] (0-1000) → {x, y, w, h} as 0..1 fractions."""
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        y0, x0, y1, x1 = (max(0.0, min(1000.0, float(v))) / 1000.0 for v in raw)
    except (TypeError, ValueError):
        return None
    if x1 <= x0 or y1 <= y0:
        return None
    return {"x": round(x0, 4), "y": round(y0, 4), "w": round(x1 - x0, 4), "h": round(y1 - y0, 4)}


def _changes(raw) -> list[str]:
    """Other differences Gemini saw between before and after, cleaned and capped."""
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for c in raw:
        text = (c.get("description") or c.get("change")) if isinstance(c, dict) else c
        text = " ".join(str(text or "").split())[:120]
        if text and text not in out:
            out.append(text)
    return out[:MAX_CHANGES]


def check_products(image: bytes, names: list[str], before: bytes | None = None) -> dict:
    """{"status": checked|skipped|error, "items": [{n, product, present, confidence, box}], "missing": [...],
    "changes": [...]}. `changes` (anything else added/removed/moved) needs the original photo as `before`."""
    names = [n for n in names if n]
    if not names:
        return {"status": "skipped", "reason": "no_products", "items": [], "missing": []}
    if not image:
        return {"status": "error", "reason": "no_image", "items": [], "missing": []}
    try:
        data = _call_gemini(image, names, before) if before else _call_gemini(image, names)
    except Exception:
        log.exception("preview QA failed")
        return {"status": "error", "reason": "qa_failed", "items": [], "missing": []}
    if data is None:
        return {"status": "skipped", "reason": "qa_unavailable", "items": [], "missing": []}
    rows = {}
    for row in data.get("items") or []:
        if not isinstance(row, dict):
            continue
        try:
            n = int(row.get("n"))
        except (TypeError, ValueError):
            continue
        rows[n] = row
    items = []
    for n, name in enumerate(names, start=1):
        row = rows.get(n) or {}
        try:
            conf = max(0.0, min(1.0, float(row.get("confidence") or 0.0)))
        except (TypeError, ValueError):
            conf = 0.0
        present = bool(row.get("present")) and conf >= PRESENT_MIN_CONFIDENCE
        items.append(
            {
                "n": n,
                "product": name,
                "present": present,
                "confidence": round(conf, 2),
                "box": _box(row.get("box_2d") or row.get("box")) if present else None,
            }
        )
    return {
        "status": "checked",
        "model": data.get("_model"),
        "items": items,
        "missing": [i["product"] for i in items if not i["present"]],
        "changes": _changes(data.get("changes")) if before else [],
    }
