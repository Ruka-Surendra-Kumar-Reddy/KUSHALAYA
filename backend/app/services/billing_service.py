from datetime import date, datetime, timedelta, timezone

from app.core.config import settings

from sqlalchemy.orm import Session

from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.core.verticals import has_feature
from app.core.vertical_guards import require_tenant_feature
from app.models.attendance_record import AttendanceRecord
from app.models.elder import Elder
from app.models.invoice import ElderBillingRate, Invoice, InvoiceLine
from app.models.user import User
from app.schemas.billing import BillingRateCreate, InvoiceGenerateRequest
from app.services.audit_service import AuditService


def _invoice_audit_snapshot(inv: Invoice) -> dict:
    return {
        "invoice_id": int(inv.id) if inv.id is not None else None,
        "invoice_number": inv.invoice_number,
        "elder_id": inv.elder_id,
        "period_start": inv.period_start.isoformat() if inv.period_start else None,
        "period_end": inv.period_end.isoformat() if inv.period_end else None,
        "status": inv.status,
        "subtotal": inv.subtotal,
        "tax_rate": inv.tax_rate,
        "tax_amount": inv.tax_amount,
        "total_amount": inv.total_amount,
        "amount_paid": inv.amount_paid,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
    }


class BillingService:

    @staticmethod
    def _assert_billing_module(db: Session, user: User) -> None:
        from app.models.tenant import Tenant

        tid = resolve_tenant_id(user)
        if tid is None:
            require_tenant_feature(db, user, "elder_billing")
            return
        tenant = db.query(Tenant).filter(Tenant.id == tid).first()
        if not tenant:
            require_tenant_feature(db, user, "elder_billing")
            return
        if has_feature(tenant.vertical, "elder_billing"):
            return
        require_tenant_feature(db, user, "elder_billing")

    @staticmethod
    def _assert_elder_billing(db: Session, user: User) -> None:
        BillingService._assert_billing_module(db, user)

    @staticmethod
    def set_billing_rate(db: Session, data: BillingRateCreate, user: User) -> ElderBillingRate:
        BillingService._assert_elder_billing(db, user)
        elder = db.query(Elder).filter(Elder.id == data.elder_id).first()
        if not elder:
            raise_not_found("Elder not found")
        assert_tenant_access(user, elder.tenant_id)

        existing = (
            db.query(ElderBillingRate)
            .filter(ElderBillingRate.elder_id == elder.id)
            .first()
        )
        if existing:
            previous_rate = existing.hourly_rate
            existing.hourly_rate = data.hourly_rate
            AuditService.log(
                db,
                tenant_id=elder.tenant_id,
                user_id=user.id,
                entity_type="elder_billing_rate",
                entity_id=int(existing.id),
                action="billing_rate_updated",
                old_value={"elder_id": elder.id, "hourly_rate": previous_rate},
                new_value={"elder_id": elder.id, "hourly_rate": data.hourly_rate},
            )
            db.commit()
            db.refresh(existing)
            return existing

        row = ElderBillingRate(
            tenant_id=elder.tenant_id,
            elder_id=elder.id,
            hourly_rate=data.hourly_rate,
        )
        db.add(row)
        db.flush()
        AuditService.log(
            db,
            tenant_id=elder.tenant_id,
            user_id=user.id,
            entity_type="elder_billing_rate",
            entity_id=int(row.id),
            action="billing_rate_created",
            old_value=None,
            new_value={"elder_id": elder.id, "hourly_rate": data.hourly_rate},
        )
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def list_billing_rates(db: Session, user: User) -> list[ElderBillingRate]:
        BillingService._assert_elder_billing(db, user)
        query = db.query(ElderBillingRate)
        tid = resolve_tenant_id(user)
        if tid is not None:
            query = query.filter(ElderBillingRate.tenant_id == tid)
        return query.all()

    @staticmethod
    def _rate_for_elder(db: Session, elder_id: int, tenant_id: int) -> float:
        row = (
            db.query(ElderBillingRate)
            .filter(ElderBillingRate.elder_id == elder_id)
            .first()
        )
        return row.hourly_rate if row else settings.DEFAULT_ELDER_HOURLY_RATE

    @staticmethod
    def generate_invoices(
        db: Session,
        data: InvoiceGenerateRequest,
        user: User,
    ) -> list[Invoice]:
        BillingService._assert_elder_billing(db, user)
        if data.period_end < data.period_start:
            raise_bad_request("period_end must be on or after period_start")

        tid = resolve_tenant_id(user)
        if tid is None and user.role != "SYSTEM_ADMIN":
            raise_bad_request("Tenant context required")
        tenant_id = tid
        if tenant_id is None:
            raise_bad_request("Tenant context required")

        period_start_dt = datetime.combine(
            data.period_start,
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
        period_end_dt = datetime.combine(
            data.period_end + timedelta(days=1),
            datetime.min.time(),
            tzinfo=timezone.utc,
        )

        by_elder_attendance: dict[int, list[AttendanceRecord]] = {}
        if data.include_attendance:
            query = db.query(AttendanceRecord).filter(
                AttendanceRecord.tenant_id == tenant_id,
                AttendanceRecord.status == "COMPLETED",
                AttendanceRecord.checkin_time >= period_start_dt,
                AttendanceRecord.checkin_time < period_end_dt,
            )
            if data.elder_id is not None:
                query = query.filter(AttendanceRecord.elder_id == data.elder_id)
            for rec in query.all():
                by_elder_attendance.setdefault(rec.elder_id, []).append(rec)

        elder_ids = set(by_elder_attendance)
        invoices: list[Invoice] = []
        for elder_id in elder_ids:
            elder_records = by_elder_attendance.get(elder_id, [])
            if not elder_records:
                continue

            existing = (
                db.query(Invoice)
                .filter(
                    Invoice.tenant_id == tenant_id,
                    Invoice.elder_id == elder_id,
                    Invoice.period_start == data.period_start,
                    Invoice.period_end == data.period_end,
                    Invoice.status == "DRAFT",
                )
                .first()
            )
            if existing:
                db.query(InvoiceLine).filter(InvoiceLine.invoice_id == existing.id).delete()
                inv = existing
            else:
                inv = Invoice(
                    tenant_id=tenant_id,
                    elder_id=elder_id,
                    period_start=data.period_start,
                    period_end=data.period_end,
                    status="DRAFT",
                )
                db.add(inv)
                db.flush()

            rate = BillingService._rate_for_elder(db, elder_id, tenant_id)
            total = 0.0
            for rec in elder_records:
                hours = (rec.visit_duration_minutes or 0) / 60.0
                if hours <= 0:
                    continue
                amount = round(hours * rate, 2)
                db.add(
                    InvoiceLine(
                        invoice_id=inv.id,
                        attendance_record_id=rec.id,
                        description=f"Care visit — caregiver #{rec.caregiver_id}",
                        hours=round(hours, 2),
                        unit_price=rate,
                        amount=amount,
                    )
                )
                total += amount

            inv.subtotal = round(total, 2)
            inv.total_amount = round(total, 2)
            invoices.append(inv)
            AuditService.log(
                db,
                tenant_id=tenant_id,
                user_id=user.id,
                entity_type="invoice",
                entity_id=int(inv.id),
                action="invoice_generated" if not existing else "invoice_regenerated",
                old_value=None,
                new_value={
                    **_invoice_audit_snapshot(inv),
                    "line_count": len([r for r in elder_records if (r.visit_duration_minutes or 0) > 0]),
                    "hourly_rate": rate,
                },
            )

        db.commit()
        for inv in invoices:
            db.refresh(inv)
        return invoices

    @staticmethod
    def list_invoices(db: Session, user: User) -> list[Invoice]:
        BillingService._assert_elder_billing(db, user)
        query = db.query(Invoice).order_by(Invoice.period_start.desc())
        tid = resolve_tenant_id(user)
        if tid is not None:
            query = query.filter(Invoice.tenant_id == tid)
        return query.limit(100).all()

    @staticmethod
    def get_invoice(db: Session, invoice_id: int, user: User) -> Invoice:
        BillingService._assert_elder_billing(db, user)
        inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not inv:
            raise_not_found("Invoice not found")
        assert_tenant_access(user, inv.tenant_id)
        return inv

    @staticmethod
    def issue_invoice(db: Session, invoice_id: int, user: User) -> Invoice:
        inv = BillingService.get_invoice(db, invoice_id, user)
        if inv.status != "DRAFT":
            raise_bad_request("Only DRAFT invoices can be issued")

        subtotal = inv.subtotal or inv.total_amount
        from app.core.markets import market_meta, tenant_market
        from app.models.tenant import Tenant

        tenant = db.query(Tenant).filter(Tenant.id == inv.tenant_id).first()
        tax_rate = market_meta(tenant_market(tenant))["default_tax_rate"]
        tax_amount = round(subtotal * tax_rate / 100.0, 2)

        before = _invoice_audit_snapshot(inv)
        inv.subtotal = round(subtotal, 2)
        inv.tax_rate = tax_rate
        inv.tax_amount = tax_amount
        inv.total_amount = round(subtotal + tax_amount, 2)
        inv.invoice_number = f"INV-{inv.tenant_id}-{inv.id:05d}"
        inv.due_date = date.today() + timedelta(
            days=settings.DEFAULT_INVOICE_PAYMENT_DAYS
        )
        inv.status = "ISSUED"
        inv.issued_at = datetime.now(timezone.utc)
        AuditService.log(
            db,
            tenant_id=inv.tenant_id,
            user_id=user.id,
            entity_type="invoice",
            entity_id=int(inv.id),
            action="invoice_issued",
            old_value=before,
            new_value=_invoice_audit_snapshot(inv),
        )
        db.commit()
        db.refresh(inv)
        return inv

    @staticmethod
    def record_payment(
        db: Session,
        invoice_id: int,
        amount: float,
        user: User,
    ) -> Invoice:
        if amount <= 0:
            raise_bad_request("Payment amount must be positive")
        inv = BillingService.get_invoice(db, invoice_id, user)
        if inv.status not in ("ISSUED", "PARTIAL", "OVERDUE"):
            raise_bad_request("Payments apply to issued invoices only")

        before = _invoice_audit_snapshot(inv)
        inv.amount_paid = round((inv.amount_paid or 0) + amount, 2)
        if inv.amount_paid >= inv.total_amount:
            inv.status = "PAID"
            inv.paid_at = datetime.now(timezone.utc)
        else:
            inv.status = "PARTIAL"
        AuditService.log(
            db,
            tenant_id=inv.tenant_id,
            user_id=user.id,
            entity_type="invoice",
            entity_id=int(inv.id),
            action="invoice_payment_recorded",
            old_value=before,
            new_value={**_invoice_audit_snapshot(inv), "payment_amount": amount},
        )
        db.commit()
        db.refresh(inv)
        return inv

    @staticmethod
    def collections_summary(db: Session, user: User) -> dict:
        from app.models.elder import Elder
        from app.services.finance_output_service import FinanceOutputService

        invoices = BillingService.list_invoices(db, user)
        today = date.today()
        buckets: dict[str, list[dict]] = {
            "current": [],
            "days_1_30": [],
            "days_31_60": [],
            "days_61_90": [],
            "over_90": [],
        }
        total_outstanding = 0.0
        overdue_count = 0

        elder_ids = {inv.elder_id for inv in invoices}
        elders = {
            e.id: e
            for e in db.query(Elder).filter(Elder.id.in_(elder_ids)).all()
        } if elder_ids else {}

        for inv in invoices:
            if inv.status in ("DRAFT", "PAID", "CANCELLED"):
                continue
            balance = round(inv.total_amount - (inv.amount_paid or 0), 2)
            if balance <= 0:
                continue

            display_status = inv.status
            if (
                inv.due_date
                and inv.due_date < today
                and inv.status in ("ISSUED", "PARTIAL")
            ):
                display_status = "OVERDUE"

            bucket = FinanceOutputService.aging_bucket(inv.due_date, today)
            elder = elders.get(inv.elder_id)
            entry = {
                "invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "elder_id": inv.elder_id,
                "elder_name": (
                    f"{elder.first_name} {elder.last_name}".strip()
                    if elder
                    else f"Elder #{inv.elder_id}"
                ),
                "due_date": inv.due_date.isoformat() if inv.due_date else None,
                "total_amount": inv.total_amount,
                "amount_paid": inv.amount_paid or 0,
                "balance": balance,
                "status": display_status,
                "days_overdue": max(
                    0,
                    (today - inv.due_date).days if inv.due_date else 0,
                ),
            }
            buckets[bucket].append(entry)
            total_outstanding += balance
            if bucket != "current":
                overdue_count += 1

        return {
            "as_of": today.isoformat(),
            "total_outstanding": round(total_outstanding, 2),
            "overdue_count": overdue_count,
            "buckets": buckets,
        }

    @staticmethod
    def lines_for_invoice(db: Session, invoice_id: int, user: User) -> list[InvoiceLine]:
        BillingService.get_invoice(db, invoice_id, user)
        return (
            db.query(InvoiceLine)
            .filter(InvoiceLine.invoice_id == invoice_id)
            .all()
        )
