"""Scheduled-style scans that emit workflow events (cert expiry, overdue follow-ups)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.workflow_events import (
    DOCUMENT_CERTIFICATION_EXPIRING,
    PROSPECT_FOLLOW_UP_OVERDUE,
)
from app.models.caregiver_certification import CaregiverCertification
from app.models.caregiver_prospect import CaregiverProspect
from app.models.elder_prospect import ElderProspect
from app.models.workflow_event import WorkflowEvent
from app.services.workflow_engine import WorkflowEngine


class WorkflowScanService:

    @staticmethod
    def _already_emitted_today(
        db: Session,
        tenant_id: int,
        event_type: str,
        entity_type: str,
        entity_id: int,
    ) -> bool:
        since = datetime.utcnow() - timedelta(hours=24)
        return (
            db.query(WorkflowEvent)
            .filter(
                WorkflowEvent.tenant_id == tenant_id,
                WorkflowEvent.event_type == event_type,
                WorkflowEvent.entity_type == entity_type,
                WorkflowEvent.entity_id == entity_id,
                WorkflowEvent.created_at >= since,
            )
            .first()
            is not None
        )

    @staticmethod
    def scan_tenant(db: Session, tenant_id: int, *, days_ahead: int = 30) -> dict:
        today = date.today()
        cutoff = today + timedelta(days=days_ahead)
        emitted: list[dict] = []

        certs = (
            db.query(CaregiverCertification)
            .filter(
                CaregiverCertification.tenant_id == tenant_id,
                CaregiverCertification.expiry_date.isnot(None),
                CaregiverCertification.expiry_date <= cutoff,
                CaregiverCertification.expiry_date >= today,
            )
            .all()
        )
        for cert in certs:
            if WorkflowScanService._already_emitted_today(
                db,
                tenant_id,
                DOCUMENT_CERTIFICATION_EXPIRING,
                "caregiver_certification",
                cert.id,
            ):
                continue
            days_until = (cert.expiry_date - today).days
            result = WorkflowEngine.emit(
                db,
                tenant_id=tenant_id,
                event_type=DOCUMENT_CERTIFICATION_EXPIRING,
                entity_type="caregiver_certification",
                entity_id=cert.id,
                payload={
                    "caregiver_id": cert.caregiver_id,
                    "certification_name": cert.certification_name,
                    "expiry_date": cert.expiry_date.isoformat(),
                    "days_until_expiry": days_until,
                    "summary": (
                        f"Certification '{cert.certification_name}' expires in {days_until} days"
                    ),
                },
            )
            emitted.append(result)

        now = datetime.utcnow()
        for model, entity_type in (
            (CaregiverProspect, "caregiver_prospect"),
            (ElderProspect, "elder_prospect"),
        ):
            rows = (
                db.query(model)
                .filter(
                    model.tenant_id == tenant_id,
                    model.next_follow_up_at.isnot(None),
                    model.next_follow_up_at < now,
                )
                .limit(50)
                .all()
            )
            for row in rows:
                if WorkflowScanService._already_emitted_today(
                    db,
                    tenant_id,
                    PROSPECT_FOLLOW_UP_OVERDUE,
                    entity_type,
                    row.id,
                ):
                    continue
                result = WorkflowEngine.emit(
                    db,
                    tenant_id=tenant_id,
                    event_type=PROSPECT_FOLLOW_UP_OVERDUE,
                    entity_type=entity_type,
                    entity_id=row.id,
                    payload={
                        "prospect_name": (
                            f"{row.first_name} {row.last_name}".strip()
                            if hasattr(row, "first_name")
                            else f"Prospect #{row.id}"
                        ),
                        "stage": getattr(row, "stage", None),
                        "next_follow_up_at": str(row.next_follow_up_at),
                        "summary": "Recruitment follow-up is overdue",
                    },
                )
                emitted.append(result)

        return {"tenant_id": tenant_id, "events_emitted": len(emitted), "results": emitted}
