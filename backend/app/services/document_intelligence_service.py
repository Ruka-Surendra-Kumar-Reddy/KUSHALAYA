"""Azure Document Intelligence OCR (optional) with dev fallback."""

import json
import logging
import re
from datetime import datetime, timezone

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _configured() -> bool:
    return bool(
        settings.DOCUMENT_INTELLIGENCE_ENDPOINT.strip()
        and settings.DOCUMENT_INTELLIGENCE_KEY.strip()
    )


def _parse_aadhaar_fields(text: str) -> dict:
    """Best-effort field extraction from OCR text."""
    out: dict[str, str] = {}
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    for line in lines:
        if re.match(r"^\d{4}\s?\d{4}\s?\d{4}$", line.replace(" ", "")):
            digits = re.sub(r"\D", "", line)
            if len(digits) == 12:
                out["aadhaar_number"] = digits
        if "male" in line.lower() and "female" not in line.lower():
            out["gender"] = "Male"
        elif "female" in line.lower():
            out["gender"] = "Female"

    dob = re.search(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b", text)
    if dob:
        out["date_of_birth"] = dob.group(1)

    if len(lines) >= 2 and "name" not in out:
        for line in lines[:5]:
            if len(line) > 3 and not line.isdigit():
                out.setdefault("full_name", line)
                break

    return {k: v for k, v in out.items() if v}


def _azure_analyze(content: bytes, content_type: str) -> dict:
    endpoint = settings.DOCUMENT_INTELLIGENCE_ENDPOINT.rstrip("/")
    key = settings.DOCUMENT_INTELLIGENCE_KEY
    api_version = settings.DOCUMENT_INTELLIGENCE_API_VERSION
    model = settings.DOCUMENT_INTELLIGENCE_MODEL

    analyze_url = (
        f"{endpoint}/documentintelligence/documentModels/{model}:analyze"
        f"?api-version={api_version}"
    )

    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": content_type or "application/octet-stream",
    }

    with httpx.Client(timeout=120.0) as client:
        start = client.post(analyze_url, headers=headers, content=content)
        start.raise_for_status()
        op_url = start.headers.get("operation-location")
        if not op_url:
            raise RuntimeError("Document Intelligence did not return operation-location")

        for _ in range(60):
            poll = client.get(op_url, headers={"Ocp-Apim-Subscription-Key": key})
            poll.raise_for_status()
            body = poll.json()
            status = body.get("status")
            if status == "succeeded":
                return body
            if status == "failed":
                raise RuntimeError(body.get("error", {}).get("message", "OCR failed"))
            import time

            time.sleep(1)

    raise RuntimeError("Document Intelligence timed out")


def _text_from_result(body: dict) -> str:
    analyze = body.get("analyzeResult") or {}
    content = analyze.get("content")
    if content:
        return content
    parts: list[str] = []
    for page in analyze.get("pages") or []:
        for line in page.get("lines") or []:
            if line.get("content"):
                parts.append(line["content"])
    return "\n".join(parts)


class DocumentIntelligenceService:

    @staticmethod
    def extract_text(content: bytes, content_type: str) -> tuple[str, str]:
        """Return (raw_text, provider) from document bytes."""
        if _configured():
            try:
                result = _azure_analyze(content, content_type)
                return _text_from_result(result), "azure_document_intelligence"
            except Exception as exc:
                logger.warning("Azure DI text extract failed: %s", exc)

        if content_type.startswith("text/"):
            try:
                return content.decode("utf-8", errors="replace"), "plain_text"
            except Exception:
                pass

        return "", "unavailable"

    @staticmethod
    def extract_identity(
        content: bytes,
        content_type: str,
        document_type: str,
    ) -> dict:
        """
        Returns OCR payload for storage on documents.ocr_extracted_json.
        """
        provider = "azure_document_intelligence" if _configured() else "dev_heuristic"
        fields: dict = {}
        raw_text = ""

        if _configured():
            try:
                result = _azure_analyze(content, content_type)
                raw_text = _text_from_result(result)
                fields = _parse_aadhaar_fields(raw_text)
                return {
                    "provider": provider,
                    "model": settings.DOCUMENT_INTELLIGENCE_MODEL,
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                    "raw_text_preview": raw_text[:2000],
                    "fields": fields,
                    "confidence": "medium",
                }
            except Exception as exc:
                logger.warning("Azure DI failed, using fallback: %s", exc)

        raw_text = f"[dev] document_type={document_type} size={len(content)}"
        if document_type in ("AADHAAR", "PAN"):
            fields = {
                "full_name": None,
                "note": "Configure DOCUMENT_INTELLIGENCE_ENDPOINT and KEY for live OCR",
            }

        return {
            "provider": "dev_heuristic",
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "raw_text_preview": raw_text,
            "fields": fields,
            "confidence": "low",
        }

    @staticmethod
    def extract_qr_stub(document_type: str) -> dict:
        """QR decode placeholder until dedicated library integrated."""
        if document_type != "AADHAAR":
            return {"status": "SKIPPED", "reason": "QR only for AADHAAR"}
        return {
            "status": "PENDING",
            "provider": "stub",
            "message": "QR extraction requires secure offline decoder integration",
            "validated": False,
        }
