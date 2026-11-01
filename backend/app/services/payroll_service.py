from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.rbac import assert_tenant_access, resolve_tenant_id
from app.core.responses import raise_bad_request, raise_not_found
from app.models.attendance_record import AttendanceRecord
from app.models.caregiver import Caregiver
from app.models.caregiver_pay_rate import CaregiverPayRate
from app.models.payroll_run import PayrollLine, PayrollRun
from app.models.tenant import Tenant
from app.models.user import User
from app.core.config import settings
from app.core.markets import market_currency, market_meta, tenant_market
from app.schemas.payroll import PayRateCreate, PayrollGenerateRequest
from app.services.statutory_payroll_service import StatutoryPayrollService


class PayrollService:

    @staticmethod
    def set_pay_rate(db: Session, data: PayRateCreate, user: User) -> CaregiverPayRate:
        caregiver = db.query(Caregiver).filter(Caregiver.id == data.caregiver_id).first()
        if not caregiver:
            raise_not_found("Caregiver not found")
        assert_tenant_access(user, caregiver.tenant_id)

        effective = data.effective_from or date.today()
        tenant = db.query(Tenant).filter(Tenant.id == caregiver.tenant_id).first()
        currency = market_currency(tenant_market(tenant)) if tenant else "INR"
        row = CaregiverPayRate(
            tenant_id=caregiver.tenant_id,
            caregiver_id=caregiver.id,
            hourly_rate=data.hourly_rate,
            currency=currency,
            effective_from=effective,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def list_pay_rates(db: Session, user: User, caregiver_id: int | None) -> list[CaregiverPayRate]:
        query = db.query(CaregiverPayRate).order_by(CaregiverPayRate.effective_from.desc())
        tid = resolve_tenant_id(user)
        if tid is not None:
            query = query.filter(CaregiverPayRate.tenant_id == tid)
        if caregiver_id is not None:
            query = query.filter(CaregiverPayRate.caregiver_id == caregiver_id)
        return query.limit(100).all()

    @staticmethod
    def _default_hourly_rate(db: Session, tenant_id: int) -> float:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant:
            return float(
                market_meta(tenant_market(tenant)).get(
                    "default_caregiver_hourly_rate",
                    settings.DEFAULT_CAREGIVER_HOURLY_RATE,
                )
            )
        return settings.DEFAULT_CAREGIVER_HOURLY_RATE

    @staticmethod
    def _rate_for_caregiver(
        db: Session,
        caregiver_id: int,
        tenant_id: int,
        on_date: date,
    ) -> float:
        row = (
            db.query(CaregiverPayRate)
            .filter(
                CaregiverPayRate.caregiver_id == caregiver_id,
                CaregiverPayRate.tenant_id == tenant_id,
                CaregiverPayRate.effective_from <= on_date,
            )
            .order_by(CaregiverPayRate.effective_from.desc())
            .first()
        )
        return row.hourly_rate if row else PayrollService._default_hourly_rate(db, tenant_id)

    @staticmethod
    def generate_run(
        db: Session,
        data: PayrollGenerateRequest,
        user: User,
    ) -> PayrollRun:
        if data.period_end < data.period_start:
            raise_bad_request("period_end must be on or after period_start")

        tid = resolve_tenant_id(user)
        if tid is None and user.role != "SYSTEM_ADMIN":
            raise_bad_request("Tenant context required")

        tenant_id = tid
        if tenant_id is None:
            raise_bad_request("Specify tenant for payroll generation")

        existing = (
            db.query(PayrollRun)
            .filter(
                PayrollRun.tenant_id == tenant_id,
                PayrollRun.period_start == data.period_start,
                PayrollRun.period_end == data.period_end,
                PayrollRun.status == "DRAFT",
            )
            .first()
        )
        if existing:
            db.query(PayrollLine).filter(PayrollLine.payroll_run_id == existing.id).delete()
            run = existing
        else:
            run = PayrollRun(
                tenant_id=tenant_id,
                period_start=data.period_start,
                period_end=data.period_end,
                status="DRAFT",
            )
            db.add(run)
            db.flush()

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

        records = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.tenant_id == tenant_id,
                AttendanceRecord.status == "COMPLETED",
                AttendanceRecord.checkin_time >= period_start_dt,
                AttendanceRecord.checkin_time < period_end_dt,
            )
            .all()
        )

        from app.services.us_compliance_helpers import is_1099_contractor

        total = 0.0
        for rec in records:
            if is_1099_contractor(db, rec.caregiver_id, tenant_id):
                continue
            hours = (rec.visit_duration_minutes or 0) / 60.0
            if hours <= 0:
                continue
            rate = PayrollService._rate_for_caregiver(
                db,
                rec.caregiver_id,
                tenant_id,
                rec.checkin_time.date() if rec.checkin_time else data.period_start,
            )
            amount = round(hours * rate, 2)
            line = PayrollLine(
                payroll_run_id=run.id,
                caregiver_id=rec.caregiver_id,
                attendance_record_id=rec.id,
                hours=round(hours, 2),
                hourly_rate=rate,
                amount=amount,
                description=f"Visit elder #{rec.elder_id}",
            )
            db.add(line)
            total += amount

        run.total_amount = round(total, 2)
        db.flush()
        StatutoryPayrollService.recompute_run(db, run)
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def get_run(db: Session, run_id: int, user: User) -> PayrollRun:
        run = db.query(PayrollRun).filter(PayrollRun.id == run_id).first()
        if not run:
            raise_not_found("Payroll run not found")
        assert_tenant_access(user, run.tenant_id)
        return run

    @staticmethod
    def list_runs(db: Session, user: User) -> list[PayrollRun]:
        query = db.query(PayrollRun).order_by(PayrollRun.period_start.desc())
        tid = resolve_tenant_id(user)
        if tid is not None:
            query = query.filter(PayrollRun.tenant_id == tid)
        return query.limit(50).all()

    @staticmethod
    def finalize_run(db: Session, run_id: int, user: User) -> PayrollRun:
        run = PayrollService.get_run(db, run_id, user)
        if run.status != "DRAFT":
            raise_bad_request("Only DRAFT payroll runs can be finalized")
        StatutoryPayrollService.recompute_run(db, run)
        run.status = "FINALIZED"
        run.finalized_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def lines_for_run(db: Session, run_id: int, user: User) -> list[PayrollLine]:
        PayrollService.get_run(db, run_id, user)
        return (
            db.query(PayrollLine)
            .filter(PayrollLine.payroll_run_id == run_id)
            .order_by(PayrollLine.caregiver_id)
            .all()
        )
