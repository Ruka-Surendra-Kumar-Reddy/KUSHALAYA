"""Caregiver portal — earnings summary and payslip access."""

from datetime import date

from sqlalchemy.orm import Session

from app.core.responses import raise_bad_request, raise_not_found
from app.models.caregiver import Caregiver
from app.models.payroll_deduction import PayrollDeduction
from app.models.payroll_run import PayrollLine, PayrollRun
from app.models.tenant import Tenant
from app.services.finance_output_service import FinanceOutputService
from app.services.statutory_payroll_service import StatutoryPayrollService


class CaregiverPayrollPortalService:

    @staticmethod
    def _lines_for_caregiver(
        db: Session,
        caregiver_id: int,
        *,
        finalized_only: bool = True,
    ) -> list[tuple[PayrollRun, PayrollLine]]:
        query = (
            db.query(PayrollRun, PayrollLine)
            .join(PayrollLine, PayrollLine.payroll_run_id == PayrollRun.id)
            .filter(PayrollLine.caregiver_id == caregiver_id)
            .order_by(PayrollRun.period_start.desc())
        )
        if finalized_only:
            query = query.filter(PayrollRun.status == "FINALIZED")
        return query.limit(200).all()

    @classmethod
    def earnings_summary(cls, db: Session, caregiver: Caregiver) -> dict:
        rows = cls._lines_for_caregiver(db, caregiver.id, finalized_only=True)
        ytd_year = date.today().year
        ytd_gross = 0.0
        ytd_net = 0.0
        ytd_hours = 0.0
        last_period: dict | None = None

        for run, line in rows:
            run_deds = (
                db.query(PayrollDeduction)
                .filter(
                    PayrollDeduction.payroll_run_id == run.id,
                    PayrollDeduction.caregiver_id == caregiver.id,
                )
                .all()
            )
            ded_total = round(sum(d.amount for d in run_deds), 2)
            net = round(line.amount - ded_total, 2)
            if run.period_start.year == ytd_year:
                ytd_gross += line.amount
                ytd_net += net
                ytd_hours += line.hours
            if last_period is None:
                last_period = {
                    "run_id": run.id,
                    "period_start": run.period_start,
                    "period_end": run.period_end,
                    "gross": round(line.amount, 2),
                    "deductions": ded_total,
                    "net": net,
                    "hours": round(line.hours, 2),
                }

        return {
            "caregiver_id": caregiver.id,
            "ytd_year": ytd_year,
            "ytd_gross": round(ytd_gross, 2),
            "ytd_net": round(ytd_net, 2),
            "ytd_hours": round(ytd_hours, 2),
            "finalized_runs_count": len({run.id for run, _ in rows}),
            "last_period": last_period,
        }

    @classmethod
    def list_payslips(cls, db: Session, caregiver: Caregiver) -> list[dict]:
        buckets: dict[int, dict] = {}
        for run, line in cls._lines_for_caregiver(db, caregiver.id, finalized_only=True):
            if run.id not in buckets:
                buckets[run.id] = {
                    "run_id": run.id,
                    "period_start": run.period_start,
                    "period_end": run.period_end,
                    "gross": 0.0,
                    "deductions": 0.0,
                    "net": 0.0,
                    "hours": 0.0,
                    "finalized_at": run.finalized_at,
                }
            buckets[run.id]["gross"] += line.amount
            buckets[run.id]["hours"] += line.hours

        for run_id, item in buckets.items():
            run_deds = (
                db.query(PayrollDeduction)
                .filter(
                    PayrollDeduction.payroll_run_id == run_id,
                    PayrollDeduction.caregiver_id == caregiver.id,
                )
                .all()
            )
            item["deductions"] = round(sum(d.amount for d in run_deds), 2)

        items = list(buckets.values())
        for item in items:
            item["gross"] = round(item["gross"], 2)
            item["hours"] = round(item["hours"], 2)
            item["net"] = round(item["gross"] - item["deductions"], 2)
        items.sort(key=lambda r: r["period_start"], reverse=True)
        return items

    @classmethod
    def payslip_pdf(cls, db: Session, caregiver: Caregiver, run_id: int) -> bytes:
        run = (
            db.query(PayrollRun)
            .filter(
                PayrollRun.id == run_id,
                PayrollRun.tenant_id == caregiver.tenant_id,
            )
            .first()
        )
        if not run:
            raise_not_found("Payroll run not found")
        if run.status != "FINALIZED":
            raise_bad_request("Payslip available after payroll is finalized")

        lines = (
            db.query(PayrollLine)
            .filter(
                PayrollLine.payroll_run_id == run_id,
                PayrollLine.caregiver_id == caregiver.id,
            )
            .all()
        )
        if not lines:
            raise_not_found("No payslip for this period")

        tenant = db.query(Tenant).filter(Tenant.id == run.tenant_id).first()
        if not tenant:
            raise_not_found("Tenant not found")

        aggregated = FinanceOutputService.aggregate_payroll(
            lines,
            {caregiver.id: caregiver},
        )
        deductions = StatutoryPayrollService.deductions_for_run(db, run_id)
        aggregated = StatutoryPayrollService.enrich_aggregated(
            aggregated,
            deductions,
        )
        return FinanceOutputService.payslip_pdf(
            tenant=tenant,
            run=run,
            caregiver_row=aggregated[0],
        )
