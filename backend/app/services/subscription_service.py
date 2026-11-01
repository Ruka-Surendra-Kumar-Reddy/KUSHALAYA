"""WorkforceOS platform subscriptions — tenant SaaS billing."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rbac import SYSTEM_ADMIN, assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.core.markets import tenant_market
from app.core.subscription_plans import DEFAULT_PILOT_BY_MARKET, DEFAULT_PLANS
from app.models.caregiver import Caregiver
from app.models.subscription_invoice import SubscriptionInvoice
from app.models.subscription_plan import SubscriptionPlan
from app.models.tenant import Tenant
from app.models.tenant_subscription import TenantSubscription
from app.models.user import User
from app.services.audit_service import AuditService


def _subscription_audit_snapshot(row: TenantSubscription | None) -> dict | None:
    if row is None:
        return None
    return {
        "subscription_id": int(row.id) if row.id is not None else None,
        "plan_id": row.plan_id,
        "status": row.status,
        "trial_ends_at": row.trial_ends_at.isoformat() if row.trial_ends_at else None,
        "current_period_start": (
            row.current_period_start.isoformat() if row.current_period_start else None
        ),
        "current_period_end": (
            row.current_period_end.isoformat() if row.current_period_end else None
        ),
        "notes": row.notes,
    }


def _subscription_invoice_audit_snapshot(inv: SubscriptionInvoice) -> dict:
    return {
        "invoice_id": int(inv.id) if inv.id is not None else None,
        "invoice_number": inv.invoice_number,
        "plan_id": inv.plan_id,
        "period_start": inv.period_start.isoformat() if inv.period_start else None,
        "period_end": inv.period_end.isoformat() if inv.period_end else None,
        "worker_count": inv.worker_count,
        "status": inv.status,
        "subtotal": inv.subtotal,
        "tax_rate": inv.tax_rate,
        "tax_amount": inv.tax_amount,
        "total_amount": inv.total_amount,
        "amount_paid": inv.amount_paid,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
    }


class SubscriptionService:

    @staticmethod
    def ensure_default_plans(db: Session) -> None:
        existing = {p.code for p in db.query(SubscriptionPlan).all()}
        added = False
        for row in DEFAULT_PLANS:
            if row["code"] not in existing:
                db.add(SubscriptionPlan(**row, is_active=True))
                added = True
        if added:
            db.commit()

    @staticmethod
    def _plan_by_code(db: Session, code: str) -> SubscriptionPlan:
        plan = (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.code == code.upper())
            .first()
        )
        if not plan:
            raise_not_found(f"Plan {code} not found")
        return plan

    @staticmethod
    def count_active_workers(db: Session, tenant_id: int) -> int:
        return (
            db.query(Caregiver)
            .filter(
                Caregiver.tenant_id == tenant_id,
                Caregiver.status == "ACTIVE",
            )
            .count()
        )

    @classmethod
    def _subscription_row(
        cls,
        db: Session,
        tenant_id: int,
        *,
        create_if_missing: bool = True,
    ) -> TenantSubscription | None:
        row = (
            db.query(TenantSubscription)
            .filter(TenantSubscription.tenant_id == tenant_id)
            .first()
        )
        if row or not create_if_missing:
            return row
        cls.ensure_default_plans(db)
        pilot = cls._plan_by_code(db, "PILOT")
        return cls.start_trial(db, tenant_id, pilot)

    @classmethod
    def start_trial(
        cls,
        db: Session,
        tenant_id: int,
        plan: SubscriptionPlan | None = None,
    ) -> TenantSubscription:
        cls.ensure_default_plans(db)
        existing = (
            db.query(TenantSubscription)
            .filter(TenantSubscription.tenant_id == tenant_id)
            .first()
        )
        if existing:
            return existing

        if plan is None:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            market = tenant_market(tenant) if tenant else "IN"
            pilot_code = DEFAULT_PILOT_BY_MARKET.get(market, "PILOT")
            plan = cls._plan_by_code(db, pilot_code)

        now = datetime.now(timezone.utc)
        trial_days = plan.trial_days or 30
        trial_end = now + timedelta(days=trial_days)
        today = date.today()
        period_end = today + timedelta(days=30)

        row = TenantSubscription(
            tenant_id=tenant_id,
            plan_id=plan.id,
            status="TRIAL",
            trial_ends_at=trial_end,
            current_period_start=today,
            current_period_end=period_end,
        )
        db.add(row)
        db.flush()
        AuditService.log(
            db,
            tenant_id=tenant_id,
            user_id=None,
            entity_type="tenant_subscription",
            entity_id=int(row.id),
            action="subscription_trial_started",
            old_value=None,
            new_value={**_subscription_audit_snapshot(row), "plan_code": plan.code},
        )
        db.commit()
        db.refresh(row)
        return row

    @classmethod
    def assign_plan(
        cls,
        db: Session,
        tenant_id: int,
        *,
        plan_code: str,
        status: str | None = None,
        notes: str | None = None,
        actor: User,
    ) -> dict:
        if actor.role != SYSTEM_ADMIN:
            raise_bad_request("Only system admins can assign subscription plans")

        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise_not_found("Tenant not found")

        plan = cls._plan_by_code(db, plan_code)
        row = cls._subscription_row(db, tenant_id, create_if_missing=False)
        today = date.today()
        before = _subscription_audit_snapshot(row)

        if row is None:
            row = TenantSubscription(
                tenant_id=tenant_id,
                plan_id=plan.id,
                status=status or "ACTIVE",
                current_period_start=today,
                current_period_end=today + timedelta(days=30),
                notes=notes,
            )
            db.add(row)
        else:
            row.plan_id = plan.id
            if status:
                row.status = status.upper()
            elif plan.trial_days > 0 and row.status == "CANCELLED":
                row.status = "TRIAL"
            elif row.status == "TRIAL" and plan.trial_days == 0:
                row.status = "ACTIVE"
            if notes is not None:
                row.notes = notes
            if plan.trial_days > 0 and row.trial_ends_at is None:
                row.trial_ends_at = datetime.now(timezone.utc) + timedelta(
                    days=plan.trial_days
                )

        db.flush()
        AuditService.log(
            db,
            tenant_id=tenant_id,
            user_id=actor.id,
            entity_type="tenant_subscription",
            entity_id=int(row.id),
            action="subscription_plan_assigned",
            old_value=before,
            new_value={**_subscription_audit_snapshot(row), "plan_code": plan.code},
        )
        db.commit()
        db.refresh(row)
        return cls._to_subscription_dict(db, row)

    @classmethod
    def _to_plan_dict(cls, plan: SubscriptionPlan) -> dict:
        return {
            "id": plan.id,
            "code": plan.code,
            "market": getattr(plan, "market", None) or "IN",
            "name": plan.name,
            "description": plan.description,
            "billing_model": plan.billing_model,
            "base_price_inr": plan.base_price_inr,
            "price_per_worker_inr": plan.price_per_worker_inr,
            "included_workers": plan.included_workers,
            "max_workers": plan.max_workers,
            "trial_days": plan.trial_days,
            "is_active": plan.is_active,
        }

    @classmethod
    def _to_subscription_dict(
        cls,
        db: Session,
        row: TenantSubscription,
    ) -> dict:
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == row.plan_id).first()
        tenant = db.query(Tenant).filter(Tenant.id == row.tenant_id).first()
        if not plan:
            raise_not_found("Subscription plan not found")
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "tenant_name": tenant.name if tenant else None,
            "plan": cls._to_plan_dict(plan),
            "status": row.status,
            "trial_ends_at": row.trial_ends_at,
            "current_period_start": row.current_period_start,
            "current_period_end": row.current_period_end,
            "active_workers": cls.count_active_workers(db, row.tenant_id),
            "notes": row.notes,
        }

    @classmethod
    def get_tenant_subscription(
        cls,
        db: Session,
        tenant_id: int,
        user: User,
    ) -> dict:
        assert_tenant_access(user, tenant_id)
        row = cls._subscription_row(db, tenant_id)
        if not row:
            raise_not_found("Subscription not found")
        return cls._to_subscription_dict(db, row)

    @classmethod
    def list_plans(cls, db: Session) -> list[SubscriptionPlan]:
        cls.ensure_default_plans(db)
        return (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.is_active.is_(True))
            .order_by(SubscriptionPlan.base_price_inr, SubscriptionPlan.id)
            .all()
        )

    @classmethod
    def compute_amount(
        cls,
        plan: SubscriptionPlan,
        worker_count: int,
    ) -> tuple[float, str]:
        model = (plan.billing_model or "PER_WORKER").upper()
        workers = max(0, worker_count)

        if model == "FLAT":
            subtotal = round(plan.base_price_inr, 2)
            desc = f"{plan.name} — flat monthly platform fee"
        elif model == "PER_WORKER":
            subtotal = round(workers * plan.price_per_worker_inr, 2)
            desc = (
                f"{plan.name} — {workers} active caregivers × "
                f"₹{plan.price_per_worker_inr:,.0f}"
            )
        else:
            overage = max(0, workers - plan.included_workers)
            subtotal = round(
                plan.base_price_inr + overage * plan.price_per_worker_inr,
                2,
            )
            desc = (
                f"{plan.name} — base ₹{plan.base_price_inr:,.0f} + "
                f"{overage} workers over {plan.included_workers} included × "
                f"₹{plan.price_per_worker_inr:,.0f}"
            )

        return subtotal, desc

    @classmethod
    def generate_invoice(
        cls,
        db: Session,
        *,
        tenant_id: int,
        period_start: date,
        period_end: date,
        actor: User,
    ) -> dict:
        if period_end < period_start:
            raise_bad_request("period_end must be on or after period_start")

        if actor.role != SYSTEM_ADMIN:
            raise_bad_request("Only system admins can generate platform invoices")

        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise_not_found("Tenant not found")

        sub = cls._subscription_row(db, tenant_id)
        if not sub:
            raise_bad_request("Tenant has no subscription")

        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.plan_id).first()
        if not plan:
            raise_not_found("Plan not found")

        existing = (
            db.query(SubscriptionInvoice)
            .filter(
                SubscriptionInvoice.tenant_id == tenant_id,
                SubscriptionInvoice.period_start == period_start,
                SubscriptionInvoice.period_end == period_end,
                SubscriptionInvoice.status.in_(("DRAFT", "ISSUED")),
            )
            .first()
        )
        if existing:
            return cls._to_invoice_dict(db, existing)

        workers = cls.count_active_workers(db, tenant_id)
        if plan.max_workers and workers > plan.max_workers:
            raise_bad_request(
                f"Active worker count {workers} exceeds plan limit {plan.max_workers}"
            )

        subtotal, line_desc = cls.compute_amount(plan, workers)
        from app.core.markets import market_meta, tenant_market

        tax_rate = market_meta(tenant_market(tenant))["default_tax_rate"]
        tax_amount = round(subtotal * tax_rate / 100.0, 2)
        total = round(subtotal + tax_amount, 2)

        inv = SubscriptionInvoice(
            tenant_id=tenant_id,
            subscription_id=sub.id,
            plan_id=plan.id,
            period_start=period_start,
            period_end=period_end,
            worker_count=workers,
            status="DRAFT",
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            total_amount=total,
        )
        db.add(inv)
        db.flush()
        AuditService.log(
            db,
            tenant_id=tenant_id,
            user_id=actor.id,
            entity_type="subscription_invoice",
            entity_id=int(inv.id),
            action="subscription_invoice_generated",
            old_value=None,
            new_value={**_subscription_invoice_audit_snapshot(inv), "line_description": line_desc},
        )
        db.commit()
        db.refresh(inv)
        result = cls._to_invoice_dict(db, inv)
        result["line_description"] = line_desc
        return result

    @classmethod
    def _to_invoice_dict(cls, db: Session, inv: SubscriptionInvoice) -> dict:
        tenant = db.query(Tenant).filter(Tenant.id == inv.tenant_id).first()
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == inv.plan_id).first()
        subtotal = inv.subtotal
        workers = inv.worker_count
        line_desc = None
        if plan:
            _, line_desc = cls.compute_amount(plan, workers)
        return {
            "id": inv.id,
            "tenant_id": inv.tenant_id,
            "tenant_name": tenant.name if tenant else None,
            "subscription_id": inv.subscription_id,
            "plan_code": plan.code if plan else None,
            "invoice_number": inv.invoice_number,
            "period_start": inv.period_start,
            "period_end": inv.period_end,
            "worker_count": inv.worker_count,
            "status": inv.status,
            "subtotal": subtotal,
            "tax_rate": inv.tax_rate,
            "tax_amount": inv.tax_amount,
            "total_amount": inv.total_amount,
            "amount_paid": inv.amount_paid,
            "due_date": inv.due_date,
            "issued_at": inv.issued_at,
            "paid_at": inv.paid_at,
            "line_description": line_desc,
        }

    @classmethod
    def list_invoices(
        cls,
        db: Session,
        user: User,
        *,
        tenant_id: int | None = None,
        status: str | None = None,
    ) -> list[dict]:
        query = db.query(SubscriptionInvoice).order_by(
            SubscriptionInvoice.period_start.desc()
        )
        tid = tenant_id or resolve_tenant_id(user)
        if user.role != SYSTEM_ADMIN:
            if tid is None:
                raise_bad_request("Tenant context required")
            query = query.filter(SubscriptionInvoice.tenant_id == tid)
        elif tid is not None:
            query = query.filter(SubscriptionInvoice.tenant_id == tid)
        if status:
            query = query.filter(SubscriptionInvoice.status == status.upper())
        return [cls._to_invoice_dict(db, inv) for inv in query.limit(100).all()]

    @classmethod
    def _next_invoice_number(cls, db: Session, tenant_id: int) -> str:
        count = (
            db.query(SubscriptionInvoice)
            .filter(SubscriptionInvoice.tenant_id == tenant_id)
            .count()
        )
        return f"WOS-{tenant_id}-{count + 1:04d}"

    @classmethod
    def issue_invoice(cls, db: Session, invoice_id: int, actor: User) -> dict:
        inv = db.query(SubscriptionInvoice).filter(SubscriptionInvoice.id == invoice_id).first()
        if not inv:
            raise_not_found("Invoice not found")
        if actor.role != SYSTEM_ADMIN:
            assert_tenant_access(actor, inv.tenant_id)
            raise_bad_request("Only system admins can issue platform invoices")
        if inv.status != "DRAFT":
            raise_bad_request("Only DRAFT invoices can be issued")

        before = _subscription_invoice_audit_snapshot(inv)
        inv.status = "ISSUED"
        inv.invoice_number = inv.invoice_number or cls._next_invoice_number(db, inv.tenant_id)
        inv.issued_at = datetime.now(timezone.utc)
        inv.due_date = date.today() + timedelta(days=settings.DEFAULT_INVOICE_PAYMENT_DAYS)

        sub = (
            db.query(TenantSubscription)
            .filter(TenantSubscription.id == inv.subscription_id)
            .first()
        )
        subscription_status_before = sub.status if sub else None
        if sub and sub.status == "TRIAL" and inv.total_amount > 0:
            sub.status = "ACTIVE"

        AuditService.log(
            db,
            tenant_id=inv.tenant_id,
            user_id=actor.id,
            entity_type="subscription_invoice",
            entity_id=int(inv.id),
            action="subscription_invoice_issued",
            old_value={**before, "subscription_status": subscription_status_before},
            new_value={
                **_subscription_invoice_audit_snapshot(inv),
                "subscription_status": sub.status if sub else None,
            },
        )
        db.commit()
        db.refresh(inv)
        return cls._to_invoice_dict(db, inv)

    @classmethod
    def record_payment(
        cls,
        db: Session,
        invoice_id: int,
        amount: float,
        actor: User,
        *,
        reference: str | None = None,
    ) -> dict:
        inv = db.query(SubscriptionInvoice).filter(SubscriptionInvoice.id == invoice_id).first()
        if not inv:
            raise_not_found("Invoice not found")
        if actor.role != SYSTEM_ADMIN:
            raise_bad_request("Only system admins can record subscription payments")
        if inv.status not in ("ISSUED", "PAID"):
            raise_bad_request("Invoice must be issued before payment")

        before = _subscription_invoice_audit_snapshot(inv)
        inv.amount_paid = round(inv.amount_paid + amount, 2)
        if inv.amount_paid >= inv.total_amount:
            inv.status = "PAID"
            inv.paid_at = datetime.now(timezone.utc)
            sub = (
                db.query(TenantSubscription)
                .filter(TenantSubscription.id == inv.subscription_id)
                .first()
            )
            if sub and sub.status == "PAST_DUE":
                sub.status = "ACTIVE"

        AuditService.log(
            db,
            tenant_id=inv.tenant_id,
            user_id=actor.id,
            entity_type="subscription_invoice",
            entity_id=int(inv.id),
            action="subscription_payment_recorded",
            old_value=before,
            new_value={
                **_subscription_invoice_audit_snapshot(inv),
                "payment_amount": amount,
                "reference": reference,
            },
        )
        db.commit()
        db.refresh(inv)
        return cls._to_invoice_dict(db, inv)

    @classmethod
    def refresh_subscription_status(cls, db: Session, tenant_id: int) -> None:
        sub = (
            db.query(TenantSubscription)
            .filter(TenantSubscription.tenant_id == tenant_id)
            .first()
        )
        if not sub:
            return

        now = datetime.now(timezone.utc)
        if sub.status == "TRIAL" and sub.trial_ends_at and sub.trial_ends_at < now:
            overdue = (
                db.query(SubscriptionInvoice)
                .filter(
                    SubscriptionInvoice.tenant_id == tenant_id,
                    SubscriptionInvoice.status == "ISSUED",
                    SubscriptionInvoice.due_date < date.today(),
                )
                .first()
            )
            sub.status = "PAST_DUE" if overdue else "ACTIVE"

        db.commit()
