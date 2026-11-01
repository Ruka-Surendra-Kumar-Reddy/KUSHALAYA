from sqlalchemy.orm import Session

from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.core.workflow_config import merge_workflow_config
from app.models.tenant import Tenant
from app.models.user import User
from app.models.workflow_event import WorkflowEvent
from app.models.workflow_task import WorkflowTask
from app.schemas.workflow import WorkflowConfigUpdate
from app.services.workflow_engine import WorkflowEngine
from app.services.workflow_scan_service import WorkflowScanService


class WorkflowService:

    @staticmethod
    def resolve_tenant_id(user: User, tenant_id: int | None) -> int:
        tid = resolve_tenant_id(user, tenant_id)
        if tid is None:
            raise_bad_request("tenant_id is required")
        return tid

    @staticmethod
    def get_config(db: Session, user: User, tenant_id: int | None = None) -> dict:
        tid = WorkflowService.resolve_tenant_id(user, tenant_id)
        tenant = db.query(Tenant).filter(Tenant.id == tid).first()
        if not tenant:
            raise_not_found("Tenant not found")
        assert_tenant_access(user, tid)
        config = merge_workflow_config(tenant.workflow_config)
        workflows = WorkflowEngine.active_workflows(db, tid)
        return {
            **config,
            "workflows": workflows,
        }

    @staticmethod
    def update_config(
        db: Session,
        user: User,
        data: WorkflowConfigUpdate,
        tenant_id: int | None = None,
    ) -> dict:
        tid = WorkflowService.resolve_tenant_id(user, tenant_id)
        tenant = db.query(Tenant).filter(Tenant.id == tid).first()
        if not tenant:
            raise_not_found("Tenant not found")
        assert_tenant_access(user, tid)

        current = merge_workflow_config(tenant.workflow_config)
        if data.disabled_workflow_ids is not None:
            current["disabled_workflow_ids"] = data.disabled_workflow_ids
        if data.channel_overrides is not None:
            current["channel_overrides"] = data.channel_overrides
        tenant.workflow_config = current
        db.commit()
        db.refresh(tenant)
        return WorkflowService.get_config(db, user, tid)

    @staticmethod
    def list_events(
        db: Session,
        user: User,
        *,
        tenant_id: int | None = None,
        limit: int = 50,
    ) -> list[WorkflowEvent]:
        tid = WorkflowService.resolve_tenant_id(user, tenant_id)
        assert_tenant_access(user, tid)
        return (
            db.query(WorkflowEvent)
            .filter(WorkflowEvent.tenant_id == tid)
            .order_by(WorkflowEvent.created_at.desc())
            .limit(min(limit, 200))
            .all()
        )

    @staticmethod
    def list_tasks(
        db: Session,
        user: User,
        *,
        tenant_id: int | None = None,
        status: str | None = "OPEN",
        limit: int = 50,
    ) -> list[WorkflowTask]:
        tid = WorkflowService.resolve_tenant_id(user, tenant_id)
        assert_tenant_access(user, tid)
        query = db.query(WorkflowTask).filter(WorkflowTask.tenant_id == tid)
        if status:
            query = query.filter(WorkflowTask.status == status.upper())
        return query.order_by(WorkflowTask.created_at.desc()).limit(min(limit, 200)).all()

    @staticmethod
    def update_task(
        db: Session,
        user: User,
        task_id: int,
        status: str,
    ) -> WorkflowTask:
        task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
        if not task:
            raise_not_found("Task not found")
        assert_tenant_access(user, task.tenant_id)
        task.status = status.upper()
        if task.status == "COMPLETED":
            from datetime import datetime

            task.completed_at = datetime.utcnow()
            task.completed_by_user_id = user.id
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    def scan(db: Session, user: User, tenant_id: int | None = None) -> dict:
        tid = WorkflowService.resolve_tenant_id(user, tenant_id)
        assert_tenant_access(user, tid)
        return WorkflowScanService.scan_tenant(db, tid)
