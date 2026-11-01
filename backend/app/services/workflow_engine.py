"""WorkforceOS workflow engine — event → matching definitions → actions."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.workflow_config import merge_workflow_config
from app.core.workflow_events import ALL_EVENT_TYPES
from app.core.workflow_templates import templates_for_vertical
from app.core.verticals import normalize_vertical
from app.models.tenant import Tenant
from app.models.workflow_event import WorkflowEvent
from app.services.workflow_actions import WorkflowActionRunner

logger = logging.getLogger(__name__)


class WorkflowEngine:

    @staticmethod
    def active_workflows(db: Session, tenant_id: int) -> list[dict]:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return []
        vertical = normalize_vertical(tenant.vertical)
        config = merge_workflow_config(tenant.workflow_config)
        disabled = set(config.get("disabled_workflow_ids") or [])
        workflows = []
        for wf in templates_for_vertical(vertical):
            enabled = wf.get("enabled_by_default", True)
            if wf["id"] in disabled:
                enabled = False
            workflows.append({**wf, "enabled": enabled})
        return workflows

    @staticmethod
    def emit(
        db: Session,
        *,
        tenant_id: int,
        event_type: str,
        entity_type: str | None = None,
        entity_id: int | None = None,
        payload: dict | None = None,
        commit: bool = True,
    ) -> dict:
        if event_type not in ALL_EVENT_TYPES:
            logger.warning("workflow_unknown_event_type %s", event_type)

        event = WorkflowEvent(
            tenant_id=tenant_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload or {},
        )
        db.add(event)
        db.flush()

        result = WorkflowEngine.process_event(db, event)
        event.processing_result = result
        if commit:
            db.commit()
            db.refresh(event)
        else:
            db.flush()
        return {
            "event_id": event.id,
            "event_type": event_type,
            **result,
        }

    @staticmethod
    def process_event(db: Session, event: WorkflowEvent) -> dict:
        tenant = db.query(Tenant).filter(Tenant.id == event.tenant_id).first()
        if not tenant:
            return {"workflows_matched": 0, "actions": [], "skipped": "tenant_not_found"}

        config = merge_workflow_config(tenant.workflow_config)
        disabled = set(config.get("disabled_workflow_ids") or [])
        vertical = normalize_vertical(tenant.vertical)

        matched_runs: list[dict] = []
        for wf in templates_for_vertical(vertical):
            if wf["id"] in disabled:
                continue
            if not wf.get("enabled_by_default", True):
                continue
            trigger = wf.get("trigger") or {}
            if trigger.get("event") != event.event_type:
                continue
            if not WorkflowEngine._conditions_match(
                wf.get("conditions") or {},
                event.payload or {},
            ):
                continue

            action_results = []
            last_task_id: int | None = None
            for action in wf.get("actions") or []:
                result = WorkflowEngine._run_action(
                    db,
                    event,
                    wf["id"],
                    action,
                    last_task_id=last_task_id,
                )
                action_results.append(result)
                if result.get("task_id"):
                    last_task_id = int(result["task_id"])
            matched_runs.append(
                {
                    "workflow_id": wf["id"],
                    "workflow_name": wf.get("name"),
                    "actions": action_results,
                }
            )

        return {
            "workflows_matched": len(matched_runs),
            "runs": matched_runs,
        }

    @staticmethod
    def _conditions_match(conditions: dict, payload: dict) -> bool:
        if conditions.get("alert_types"):
            alert = (payload.get("alert_type") or "").upper()
            allowed = {a.upper() for a in conditions["alert_types"]}
            if alert not in allowed:
                return False

        max_days = conditions.get("max_days_until_expiry")
        if max_days is not None:
            days = payload.get("days_until_expiry")
            if days is None or days > max_days:
                return False

        min_severity = conditions.get("min_severity")
        if min_severity:
            sev = (payload.get("severity") or "").upper()
            order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
            if order.get(sev, 0) < order.get(min_severity.upper(), 0):
                return False

        return True

    @staticmethod
    def _run_action(
        db: Session,
        event: WorkflowEvent,
        workflow_id: str,
        action: dict,
        *,
        last_task_id: int | None = None,
    ) -> dict:
        action_type = action.get("type")
        try:
            if action_type == "notify_roles":
                return WorkflowActionRunner.notify_roles(
                    db, event.tenant_id, event, action, workflow_id
                )
            if action_type == "create_task":
                return WorkflowActionRunner.create_task(
                    db, event.tenant_id, event, action, workflow_id
                )
            if action_type == "suggest_replacement":
                return WorkflowActionRunner.suggest_replacement(
                    db,
                    event.tenant_id,
                    event,
                    action,
                    workflow_id,
                    task_id=last_task_id,
                )
            return {"type": action_type, "status": "unsupported"}
        except Exception:
            logger.exception(
                "workflow_action_failed workflow=%s action=%s",
                workflow_id,
                action_type,
            )
            return {"type": action_type, "status": "error"}
