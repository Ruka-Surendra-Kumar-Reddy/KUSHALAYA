"""Safe workflow event emission from domain services."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.services.workflow_engine import WorkflowEngine

logger = logging.getLogger(__name__)


def emit_workflow_event(
    db: Session,
    *,
    tenant_id: int,
    event_type: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    payload: dict | None = None,
    commit: bool = True,
) -> dict | None:
    try:
        return WorkflowEngine.emit(
            db,
            tenant_id=tenant_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            commit=commit,
        )
    except Exception:
        logger.exception(
            "workflow_emit_failed tenant=%s event=%s",
            tenant_id,
            event_type,
        )
        return None
