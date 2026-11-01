from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import CARE_MANAGER, READ_ROLES, TENANT_ADMIN, SYSTEM_ADMIN, require_roles
from app.models.user import User
from app.schemas.workflow import (
    WorkflowConfigResponse,
    WorkflowConfigUpdate,
    WorkflowEventResponse,
    WorkflowScanResponse,
    WorkflowTaskResponse,
    WorkflowTaskUpdate,
)
from app.services.workflow_service import WorkflowService

router = APIRouter(prefix="/workflows", tags=["Workflow Automation"])


@router.get("/definitions", response_model=WorkflowConfigResponse)
def get_workflow_definitions(
    tenant_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return WorkflowService.get_config(db, current_user, tenant_id)


@router.patch("/definitions", response_model=WorkflowConfigResponse)
def update_workflow_definitions(
    data: WorkflowConfigUpdate,
    tenant_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(TENANT_ADMIN, SYSTEM_ADMIN)),
):
    return WorkflowService.update_config(db, current_user, data, tenant_id)


@router.get("/events", response_model=list[WorkflowEventResponse])
def list_workflow_events(
    tenant_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return WorkflowService.list_events(
        db, current_user, tenant_id=tenant_id, limit=limit
    )


@router.get("/tasks", response_model=list[WorkflowTaskResponse])
def list_workflow_tasks(
    tenant_id: int | None = Query(default=None),
    status: str | None = Query(default="OPEN"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return WorkflowService.list_tasks(
        db, current_user, tenant_id=tenant_id, status=status, limit=limit
    )


@router.patch("/tasks/{task_id}", response_model=WorkflowTaskResponse)
def update_workflow_task(
    task_id: int,
    data: WorkflowTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    if not data.status:
        from app.core.responses import raise_bad_request

        raise_bad_request("status is required")
    return WorkflowService.update_task(db, current_user, task_id, data.status)


@router.post("/scan", response_model=WorkflowScanResponse)
def scan_workflow_triggers(
    tenant_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(TENANT_ADMIN, SYSTEM_ADMIN, CARE_MANAGER)
    ),
):
    return WorkflowService.scan(db, current_user, tenant_id)
