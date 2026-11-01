"""Checkr background-check webhook handler."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.us_workforce_compliance import USWorkforceCompliance

logger = logging.getLogger(__name__)

# Checkr report statuses → our compliance status
CHECKR_STATUS_MAP: dict[str, str] = {
    "clear": "VERIFIED",
    "consider": "REVIEW",
    "suspended": "REVIEW",
    "pending": "PENDING",
    "dispute": "REVIEW",
}


class CheckrWebhookService:

    @staticmethod
    def verify_secret(header_value: str | None) -> bool:
        secret = getattr(settings, "CHECKR_WEBHOOK_SECRET", "") or ""
        if not secret:
            return True
        return header_value == secret

    @classmethod
    def process_payload(cls, db: Session, payload: dict) -> dict:
        """
        Accept Checkr-style webhook payloads.

        Expected fields (flexible):
        - type: e.g. report.completed
        - data.object.id / candidate_id / report_id
        - data.object.status / result
        """
        event_type = payload.get("type") or payload.get("event_type") or ""
        data = payload.get("data") or {}
        obj = data.get("object") if isinstance(data.get("object"), dict) else data

        provider_ref = (
            obj.get("id")
            or obj.get("candidate_id")
            or obj.get("report_id")
            or payload.get("candidate_id")
            or payload.get("report_id")
        )
        raw_status = (
            obj.get("status")
            or obj.get("result")
            or payload.get("status")
            or ""
        )
        status_key = str(raw_status).lower().strip()
        mapped = CHECKR_STATUS_MAP.get(status_key, "REVIEW")

        if not provider_ref:
            logger.warning("Checkr webhook missing provider ref: %s", payload)
            return {"ok": False, "reason": "missing_provider_ref"}

        row = (
            db.query(USWorkforceCompliance)
            .filter(
                USWorkforceCompliance.background_check_provider_ref == str(provider_ref)
            )
            .first()
        )
        if not row:
            row = (
                db.query(USWorkforceCompliance)
                .filter(
                    USWorkforceCompliance.background_check_provider_ref.is_(None),
                )
                .first()
            )
            if row and obj.get("custom_id"):
                try:
                    cg_id = int(obj["custom_id"])
                    if row.caregiver_id == cg_id:
                        row.background_check_provider_ref = str(provider_ref)
                except (TypeError, ValueError):
                    pass

        if not row:
            logger.info(
                "Checkr webhook: no compliance row for ref %s (event=%s)",
                provider_ref,
                event_type,
            )
            return {
                "ok": True,
                "updated": False,
                "provider_ref": str(provider_ref),
                "event_type": event_type,
            }

        row.background_check_provider_ref = str(provider_ref)
        row.background_check_status = mapped
        db.commit()

        return {
            "ok": True,
            "updated": True,
            "caregiver_id": row.caregiver_id,
            "background_check_status": mapped,
            "provider_ref": str(provider_ref),
            "event_type": event_type,
        }
