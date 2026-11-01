"""Workflow action handlers — notify, create task."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workflow_event import WorkflowEvent
from app.models.workflow_task import WorkflowTask
from app.services.notifications import get_email_provider, get_sms_provider

logger = logging.getLogger(__name__)


class WorkflowActionRunner:

    @staticmethod
    def notify_roles(
        db: Session,
        tenant_id: int,
        event: WorkflowEvent,
        action: dict,
        workflow_id: str,
    ) -> dict:
        roles = action.get("roles") or ["CARE_MANAGER"]
        channels = action.get("channels") or ["email"]
        subject = action.get("subject") or f"Workflow: {event.event_type}"
        message = WorkflowActionRunner._format_message(event, workflow_id)

        users = (
            db.query(User)
            .filter(
                User.tenant_id == tenant_id,
                User.role.in_(roles),
                User.status == "ACTIVE",
            )
            .limit(10)
            .all()
        )

        email_provider = get_email_provider()
        deliveries: list[dict] = []

        for user in users:
            for channel in channels:
                ch = channel.lower()
                if ch == "email" and user.email:
                    result = email_provider.send(
                        to=user.email,
                        subject=subject,
                        body=message,
                    )
                    deliveries.append(
                        {
                            "channel": "email",
                            "recipient": user.email,
                            "status": result.status,
                        }
                    )
                elif ch == "sms":
                    # Staff users have email only today; SMS logs for audit until phone on User.
                    logger.info(
                        "workflow_sms_log tenant=%s workflow=%s -> %s",
                        tenant_id,
                        workflow_id,
                        user.email,
                    )
                    deliveries.append(
                        {
                            "channel": "sms",
                            "recipient": user.email,
                            "status": "LOGGED",
                        }
                    )
                else:
                    logger.info(
                        "workflow_notify_log tenant=%s workflow=%s %s -> %s",
                        tenant_id,
                        workflow_id,
                        ch,
                        user.email,
                    )
                    deliveries.append(
                        {
                            "channel": ch,
                            "recipient": user.email or user.phone or str(user.id),
                            "status": "LOGGED",
                        }
                    )

        return {"type": "notify_roles", "deliveries": deliveries}

    @staticmethod
    def create_task(
        db: Session,
        tenant_id: int,
        event: WorkflowEvent,
        action: dict,
        workflow_id: str,
    ) -> dict:
        roles = action.get("assign_roles") or ["CARE_MANAGER"]
        task = WorkflowTask(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            workflow_event_id=event.id,
            title=action.get("title") or "Workflow follow-up",
            description=WorkflowActionRunner._format_message(event, workflow_id),
            priority=(action.get("priority") or "NORMAL").upper(),
            status="OPEN",
            assign_roles=",".join(roles),
        )
        db.add(task)
        db.flush()
        return {"type": "create_task", "task_id": task.id}

    @staticmethod
    def suggest_replacement(
        db: Session,
        tenant_id: int,
        event: WorkflowEvent,
        action: dict,
        workflow_id: str,
        *,
        task_id: int | None = None,
    ) -> dict:
        from app.models.workflow_task import WorkflowTask
        from app.services.replacement_staffing_service import (
            ReplacementStaffingService,
        )

        payload = event.payload or {}
        elder_id = payload.get("elder_id")
        if not elder_id:
            return {"type": "suggest_replacement", "status": "skipped", "reason": "no_elder_id"}

        suggestions = ReplacementStaffingService.suggest_replacements(
            db,
            tenant_id,
            int(elder_id),
            exclude_caregiver_id=payload.get("caregiver_id"),
            limit=int(action.get("limit") or 5),
            min_score=float(action.get("min_score") or 40),
        )

        task = None
        if task_id is not None:
            task = (
                db.query(WorkflowTask)
                .filter(
                    WorkflowTask.id == task_id,
                    WorkflowTask.tenant_id == tenant_id,
                )
                .first()
            )
        if task is None and event.id:
            task = (
                db.query(WorkflowTask)
                .filter(
                    WorkflowTask.workflow_event_id == event.id,
                    WorkflowTask.tenant_id == tenant_id,
                )
                .order_by(WorkflowTask.id.desc())
                .first()
            )

        meta = {
            "replacement_suggestions": suggestions,
            "attendance": {
                "alert_type": payload.get("alert_type"),
                "elder_id": elder_id,
                "caregiver_id": payload.get("caregiver_id"),
                "assignment_id": payload.get("assignment_id"),
            },
        }
        if task:
            task.metadata_json = meta
            if suggestions["suggestions"]:
                names = ", ".join(
                    s["caregiver_name"] for s in suggestions["suggestions"][:3]
                )
                task.description = (
                    (task.description or "")
                    + f"\n\nReplacement options: {names}"
                ).strip()
            db.flush()

        return {
            "type": "suggest_replacement",
            "task_id": task.id if task else None,
            "suggestion_count": len(suggestions["suggestions"]),
            "bench_available": suggestions["bench_available"],
        }

    @staticmethod
    def _format_message(event: WorkflowEvent, workflow_id: str) -> str:
        payload = event.payload or {}
        lines = [
            f"Workflow: {workflow_id}",
            f"Event: {event.event_type}",
        ]
        if event.entity_type and event.entity_id:
            lines.append(f"Entity: {event.entity_type} #{event.entity_id}")
        for key in ("message", "summary", "alert_type", "incident_type", "body"):
            if payload.get(key):
                lines.append(f"{key}: {payload[key]}")
        return "\n".join(lines)
