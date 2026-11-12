"""Operations board (leads by stage) and customer plans. Logic: app/livewell/sales_pipeline.py."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import ADMIN_ROLES, READ_ROLES, WRITE_ROLES, require_roles
from app.livewell import sales_pipeline as sp
from app.models.user import User

router = APIRouter(prefix="/sales", tags=["Operations board / Customer plans"])


class LeadIn(BaseModel):
    name: str = Field(max_length=200)
    source: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)


class MoveIn(BaseModel):
    to: str = Field(max_length=40)
    comment: str | None = Field(default=None, max_length=4000)
    plan_id: str | None = Field(default=None, max_length=40)
    billing_cycle: str | None = Field(default=None, max_length=10)
    start_date: date | None = None
    elder_id: int | None = None
    coupon_code: str | None = Field(default=None, max_length=40)


class PlanIn(BaseModel):
    plan_id: str = Field(max_length=40)
    billing_cycle: str = Field(max_length=10)
    start_date: date | None = None
    coupon_code: str | None = Field(default=None, max_length=40)


class AuthorizeIn(BaseModel):
    payment_mode: str = Field(max_length=30)
    paid: bool = False


class MarkPaidIn(BaseModel):
    payment_mode: str | None = Field(default=None, max_length=30)


class CommentIn(BaseModel):
    comment: str = Field(max_length=4000)


@router.get("/leads")
def list_leads(
    created_from: datetime | None = Query(default=None, alias="from"),
    created_to: datetime | None = Query(default=None, alias="to"),
    all_time: bool = Query(default=False, alias="all"),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*READ_ROLES)),
):
    """``from`` / ``to``: ISO date-times on the lead's created time (``to`` is exclusive)."""
    return sp.list_leads(db, user, created_from=created_from, created_to=created_to, all_time=all_time)


@router.post("/leads/{lead_id}/comment", status_code=201)
def add_comment(lead_id: int, data: CommentIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    return sp.add_comment(db, user, lead_id, data.comment)


@router.post("/leads", status_code=201)
def create_lead(data: LeadIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    return sp.create_lead(db, user, name=data.name, source=data.source, phone=data.phone, email=data.email)


@router.get("/leads/{lead_id}/history")
def lead_history(lead_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return sp.lead_history(db, user, lead_id)


@router.post("/leads/{lead_id}/move")
def move_lead(lead_id: int, data: MoveIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    return sp.move_lead(
        db, user, lead_id,
        to=data.to, comment=data.comment, plan_id=data.plan_id,
        billing_cycle=data.billing_cycle, start_date=data.start_date, elder_id=data.elder_id,
        coupon_code=data.coupon_code,
    )


class PlanPriceIn(BaseModel):
    plan_id: str = Field(max_length=40)
    billing_cycle: str = Field(max_length=10)
    coupon_code: str | None = Field(default=None, max_length=40)


@router.post("/plan-price")
def plan_price(data: PlanPriceIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    """Price of a plan with an optional coupon, for the Won / assign-plan forms (nothing is saved)."""
    return sp.price_plan(db, user.tenant_id, data.plan_id, data.billing_cycle, data.coupon_code)


@router.get("/dashboard-counts")
def dashboard_counts(db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return sp.dashboard_counts(db, user)


@router.get("/customers")
def list_customers(db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return sp.list_customers(db, user)


@router.get("/customers/{elder_id}/plans")
def customer_plans(elder_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return sp.elder_plans(db, user, elder_id)


@router.post("/customers/{elder_id}/plans", status_code=201)
def assign_plan(elder_id: int, data: PlanIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    return sp.assign_plan(db, user, elder_id, plan_id=data.plan_id, billing_cycle=data.billing_cycle, start_date=data.start_date,
                          coupon_code=data.coupon_code)


@router.post("/plans/{plan_row_id}/authorize")
def authorize_plan(
    plan_row_id: int, data: AuthorizeIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))
):
    """Approval step: admins only (a manager can win the deal, an admin turns the plan on)."""
    return sp.authorize(db, user, plan_row_id, payment_mode=data.payment_mode, paid=data.paid)


@router.post("/plans/{plan_row_id}/mark-paid")
def mark_paid(plan_row_id: int, data: MarkPaidIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*WRITE_ROLES))):
    return sp.mark_paid(db, user, plan_row_id, payment_mode=data.payment_mode)


class TargetsIn(BaseModel):
    month: str = Field(max_length=7)
    user_id: int
    targets: dict[str, int | None]


@router.get("/targets")
def get_targets(
    month: str | None = Query(default=None, max_length=7),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*READ_ROLES)),
):
    """Team targets: KPI, target, achieved and % for the month. Admins see everyone."""
    from app.core.rbac import resolve_tenant_id
    from app.core.responses import raise_bad_request
    from app.livewell import sales_targets as st

    tid = resolve_tenant_id(user) or user.tenant_id
    month = month or st.current_month()
    try:
        st.month_bounds(month)
    except ValueError as e:
        raise_bad_request(str(e))
    return st.report(db, user, tid, month, everyone=user.role in ADMIN_ROLES)


@router.put("/targets")
def put_targets(data: TargetsIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_ROLES))):
    from app.core.rbac import resolve_tenant_id
    from app.core.responses import raise_bad_request
    from app.livewell import sales_targets as st
    from app.models.tenant import Tenant

    tid = resolve_tenant_id(user) or user.tenant_id
    person = db.get(User, data.user_id)
    if person is None or person.tenant_id != tid:
        raise_bad_request("Choose someone from your team.")
    try:
        st.save_targets(db, db.get(Tenant, tid), data.month, data.user_id, data.targets)
    except ValueError as e:
        raise_bad_request(str(e))
    return st.report(db, user, tid, data.month, everyone=True)
