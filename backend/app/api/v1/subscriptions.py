from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import CARE_MANAGER, READ_ROLES, SYSTEM_ADMIN, TENANT_ADMIN, require_roles, resolve_tenant_id
from app.models.user import User
from app.schemas.subscription import (
    AssignSubscriptionRequest,
    SubscriptionInvoiceGenerateRequest,
    SubscriptionInvoiceResponse,
    SubscriptionPaymentCreate,
    SubscriptionPlanResponse,
    TenantSubscriptionResponse,
)
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["Platform Subscriptions"])


@router.get("/plans", response_model=list[SubscriptionPlanResponse])
def list_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return SubscriptionService.list_plans(db)


@router.get("/me", response_model=TenantSubscriptionResponse)
def my_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN, TENANT_ADMIN, CARE_MANAGER)),
):
    tid = resolve_tenant_id(current_user)
    if tid is None:
        from app.core.responses import raise_bad_request

        raise_bad_request("No tenant assigned — use admin tenant subscription API")
    return SubscriptionService.get_tenant_subscription(db, tid, current_user)


@router.get("/invoices", response_model=list[SubscriptionInvoiceResponse])
def list_invoices(
    status: str | None = Query(default=None),
    tenant_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN, TENANT_ADMIN, CARE_MANAGER)),
):
    return SubscriptionService.list_invoices(
        db,
        current_user,
        tenant_id=tenant_id,
        status=status,
    )


@router.post("/invoices/generate", response_model=SubscriptionInvoiceResponse)
def generate_invoice(
    data: SubscriptionInvoiceGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN)),
):
    tid = data.tenant_id
    if tid is None:
        from app.core.responses import raise_bad_request

        raise_bad_request("tenant_id is required")
    return SubscriptionService.generate_invoice(
        db,
        tenant_id=tid,
        period_start=data.period_start,
        period_end=data.period_end,
        actor=current_user,
    )


@router.post("/invoices/{invoice_id}/issue", response_model=SubscriptionInvoiceResponse)
def issue_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN)),
):
    return SubscriptionService.issue_invoice(db, invoice_id, current_user)


@router.post("/invoices/{invoice_id}/payments", response_model=SubscriptionInvoiceResponse)
def record_payment(
    invoice_id: int,
    data: SubscriptionPaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN)),
):
    return SubscriptionService.record_payment(
        db,
        invoice_id,
        data.amount,
        current_user,
        reference=data.reference,
    )


@router.get(
    "/admin/tenants/{tenant_id}",
    response_model=TenantSubscriptionResponse,
)
def admin_get_tenant_subscription(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN)),
):
    return SubscriptionService.get_tenant_subscription(db, tenant_id, current_user)


@router.put(
    "/admin/tenants/{tenant_id}",
    response_model=TenantSubscriptionResponse,
)
def admin_assign_subscription(
    tenant_id: int,
    data: AssignSubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(SYSTEM_ADMIN)),
):
    return SubscriptionService.assign_plan(
        db,
        tenant_id,
        plan_code=data.plan_code,
        status=data.status,
        notes=data.notes,
        actor=current_user,
    )
