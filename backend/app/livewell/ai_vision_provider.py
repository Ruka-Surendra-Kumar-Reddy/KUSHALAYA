"""Contract C — room photo analysis via Gemini 2.5 Flash (hosted vision)."""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.ai_visualization_contracts import (
    RoomAnalyzeRequest,
    RoomAnalyzeResponse,
    RoomObservation,
    RoomType,
)

logger = logging.getLogger(__name__)

GEMINI_GENERATE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


class VisionProvider(ABC):
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def model_version(self) -> str:
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        pass

    @abstractmethod
    def analyze_room(
        self,
        request: RoomAnalyzeRequest,
        *,
        image_bytes_by_photo_id: dict[str, bytes],
        allowed_finding_codes: list[str],
        assessor_confirm_min: float = 0.6,
    ) -> RoomAnalyzeResponse:
        pass


class NotConfiguredVisionProvider(VisionProvider):
    def name(self) -> str:
        return "none"

    def model_version(self) -> str:
        return "none"

    def is_configured(self) -> bool:
        return False

    def analyze_room(
        self,
        request: RoomAnalyzeRequest,
        *,
        image_bytes_by_photo_id: dict[str, bytes],
        allowed_finding_codes: list[str],
        assessor_confirm_min: float = 0.6,
    ) -> RoomAnalyzeResponse:
        del image_bytes_by_photo_id, allowed_finding_codes, assessor_confirm_min
        return RoomAnalyzeResponse(
            job_id=request.job_id,
            status="FAILED",
            model_versions={"provider": self.name()},
            observations=[],
            surfaces=[],
            limitations=["VISION_PROVIDER_NOT_CONFIGURED"],
        )


class GeminiFlashVisionProvider(VisionProvider):
    """Google Gemini 2.5 Flash — structured hazard observations only."""

    def __init__(self, *, model: str | None = None, api_key: str | None = None) -> None:
        self._model = (model or settings.AI_VISION_MODEL or "gemini-3.5-flash").strip()
        self._api_key = (api_key if api_key is not None else settings.GEMINI_API_KEY).strip()

    def name(self) -> str:
        return "gemini"

    def model_version(self) -> str:
        return self._model

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def analyze_room(
        self,
        request: RoomAnalyzeRequest,
        *,
        image_bytes_by_photo_id: dict[str, bytes],
        allowed_finding_codes: list[str],
        assessor_confirm_min: float = 0.6,
    ) -> RoomAnalyzeResponse:
        if not self.is_configured():
            return NotConfiguredVisionProvider().analyze_room(
                request,
                image_bytes_by_photo_id=image_bytes_by_photo_id,
                allowed_finding_codes=allowed_finding_codes,
                assessor_confirm_min=assessor_confirm_min,
            )

        allowed = [c for c in allowed_finding_codes if c]
        room_label = (
            request.room_type.value
            if isinstance(request.room_type, RoomType)
            else str(request.room_type)
        )
        parts: list[dict[str, Any]] = [
            {
                "text": (
                    "You are a home-safety assessor assistant. Analyze the room photo(s).\n"
                    f"Room type: {room_label}.\n"
                    "Return ONLY JSON with this shape:\n"
                    '{"observations":[{"observation_code":"...","evidence":"...","photo_id":"...",'
                    '"confidence":0.0}],"limitations":["..."]}\n'
                    "Rules:\n"
                    f"- observation_code MUST be one of: {json.dumps(allowed)}\n"
                    "- If you see a hazard not in that list, put a short note in limitations — "
                    "do NOT invent new observation_code values.\n"
                    "- confidence is 0.0–1.0.\n"
                    "- photo_id must match one of the provided photo ids when possible.\n"
                    "- Do not invent products or SKUs.\n"
                )
            }
        ]

        for ref in request.source_images:
            raw = image_bytes_by_photo_id.get(ref.photo_id)
            if not raw:
                continue
            mime = "image/jpeg"
            # Prefer png detection from magic bytes
            if raw[:8] == b"\x89PNG\r\n\x1a\n":
                mime = "image/png"
            elif raw[:2] == b"\xff\xd8":
                mime = "image/jpeg"
            parts.append({"text": f"photo_id={ref.photo_id}"})
            parts.append(
                {
                    "inline_data": {
                        "mime_type": mime,
                        "data": base64.b64encode(raw).decode("ascii"),
                    }
                }
            )

        if len(parts) <= 1:
            return RoomAnalyzeResponse(
                job_id=request.job_id,
                status="FAILED",
                model_versions={"provider": self.name(), "model": self._model},
                limitations=["SOURCE_IMAGE_MISSING"],
            )

        url = GEMINI_GENERATE_URL.format(model=self._model)
        body = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        try:
            with httpx.Client(timeout=90.0) as client:
                resp = client.post(url, params={"key": self._api_key}, json=body)
                if resp.status_code >= 400:
                    logger.warning(
                        "Gemini vision failed HTTP %s: %s",
                        resp.status_code,
                        resp.text[:300],
                    )
                    return RoomAnalyzeResponse(
                        job_id=request.job_id,
                        status="FAILED",
                        model_versions={"provider": self.name(), "model": self._model},
                        limitations=[f"GEMINI_HTTP_{resp.status_code}"],
                    )
                payload = resp.json()
        except Exception as exc:
            logger.exception("Gemini vision request error")
            return RoomAnalyzeResponse(
                job_id=request.job_id,
                status="FAILED",
                model_versions={"provider": self.name(), "model": self._model},
                limitations=[f"GEMINI_ERROR:{exc}"],
            )

        parsed = _extract_gemini_json(payload)
        allowed_set = set(allowed)
        observations: list[RoomObservation] = []
        for row in parsed.get("observations") or []:
            if not isinstance(row, dict):
                continue
            code = str(row.get("observation_code") or "").strip()
            if not code or code not in allowed_set:
                continue
            try:
                conf = float(row.get("confidence") or 0.0)
            except (TypeError, ValueError):
                conf = 0.0
            conf = max(0.0, min(1.0, conf))
            observations.append(
                RoomObservation(
                    observation_code=code,
                    evidence=(str(row.get("evidence")).strip() if row.get("evidence") else None),
                    photo_id=(str(row.get("photo_id")).strip() if row.get("photo_id") else None),
                    confidence=conf,
                    requires_human_verification=conf < float(assessor_confirm_min),
                )
            )

        limitations = [
            str(x).strip()
            for x in (parsed.get("limitations") or [])
            if str(x).strip()
        ]
        return RoomAnalyzeResponse(
            job_id=request.job_id,
            status="SUCCEEDED",
            model_versions={"provider": self.name(), "model": self._model},
            observations=observations,
            surfaces=[],
            limitations=limitations,
        )


def _extract_gemini_json(payload: dict) -> dict:
    try:
        candidates = payload.get("candidates") or []
        parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
        text = ""
        for part in parts:
            if isinstance(part, dict) and part.get("text"):
                text += str(part["text"])
        text = text.strip()
        if not text:
            return {}
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].lstrip()
        return json.loads(text)
    except Exception:
        return {}


def get_vision_provider(settings_dict: dict | None = None) -> VisionProvider:
    cfg = settings_dict or {}
    provider_id = str(
        cfg.get("vision_provider")
        or settings.AI_VISION_PROVIDER
        or "gemini"
    ).strip().lower()
    if provider_id in ("none", "off", "disabled", ""):
        return NotConfiguredVisionProvider()
    model = str(cfg.get("vision_model") or settings.AI_VISION_MODEL or "gemini-3.5-flash")
    if provider_id in ("gemini", "gemini_flash", "google"):
        return GeminiFlashVisionProvider(model=model)
    return NotConfiguredVisionProvider()


def guess_image_mime(data: bytes, fallback: str = "image/jpeg") -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    guessed, _ = mimetypes.guess_type("x.jpg")
    return guessed or fallback
