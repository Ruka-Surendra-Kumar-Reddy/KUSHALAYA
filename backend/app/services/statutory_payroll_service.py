"""Statutory payroll deductions — routes by tenant market (IN / US)."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.csv_safe import SafeWriter
from app.core.markets import MARKET_US, tenant_market
from app.models.caregiver import Caregiver
from app.models.payroll_deduction import PayrollDeduction
from app.models.payroll_run import PayrollLine, PayrollRun
from app.models.tenant import Tenant
from app.services.finance_output_service import FinanceOutputService

DEDUCTION_PF = "PF"
DEDUCTION_ESI = "ESI"
DEDUCTION_PT = "PROFESSIONAL_TAX"
DEDUCTION_TDS = "TDS"

DEFAULT_PAYROLL_CONFIG = {
    "statutory_enabled": True,
    "pf_employee_rate": 0.12,
    "pf_wage_ceiling_monthly_inr": 15_000.0,
    "esi_employee_rate": 0.0075,
    "esi_gross_ceiling_monthly_inr": 21_000.0,
    "professional_tax_monthly_inr": 200.0,
    "tds_annual_threshold_inr": 250_000.0,
    "tds_rate": 0.05,
}


class StatutoryPayrollService:

    @staticmethod
    def _period_days(period_start: date, period_end: date) -> int:
        return (period_end - period_start).days + 1

    @staticmethod
    def _prorate_monthly(amount: float, period_start: date, period_end: date) -> float:
        days = StatutoryPayrollService._period_days(period_start, period_end)
        return round(amount * days / 30.0, 2)

    @staticmethod
    def _config(tenant: Tenant) -> dict:
        raw = getattr(tenant, "payroll_config", None) or {}
        merged = {**DEFAULT_PAYROLL_CONFIG, **raw}
        return merged

    @staticmethod
    def _caregiver_profile(caregiver: Caregiver) -> dict:
        attrs = caregiver.custom_attributes or {}
        return attrs.get("payroll") or {}

    @staticmethod
    def _applicable(profile: dict, key: str, default: bool = True) -> bool:
        if key in profile:
            return bool(profile[key])
        return default

    @staticmethod
    def _fy_start(for_date: date) -> date:
        if for_date.month >= 4:
            return date(for_date.year, 4, 1)
        return date(for_date.year - 1, 4, 1)

    @classmethod
    def _ytd_gross(
        cls,
        db: Session,
        caregiver_id: int,
        tenant_id: int,
        before_period_start: date,
    ) -> float:
        fy_start = cls._fy_start(before_period_start)
        rows = (
            db.query(PayrollLine.amount)
            .join(PayrollRun, PayrollRun.id == PayrollLine.payroll_run_id)
            .filter(
                PayrollLine.caregiver_id == caregiver_id,
                PayrollRun.tenant_id == tenant_id,
                PayrollRun.status == "FINALIZED",
                PayrollRun.period_end >= fy_start,
                PayrollRun.period_end < before_period_start,
            )
            .all()
        )
        return round(sum(r[0] for r in rows), 2)

    @classmethod
    def compute_for_caregiver(
        cls,
        *,
        gross: float,
        caregiver: Caregiver,
        tenant: Tenant,
        run: PayrollRun,
        ytd_gross_before: float,
        db: Session | None = None,
    ) -> list[dict]:
        if db is not None:
            from app.services.us_compliance_helpers import is_1099_contractor

            if is_1099_contractor(db, caregiver.id, tenant.id):
                return []

        if tenant_market(tenant) == MARKET_US:
            from app.services.us_statutory_payroll_service import USStatutoryPayrollService

            ytd = ytd_gross_before
            if db is not None and ytd == 0:
                ytd = USStatutoryPayrollService._ytd_gross(
                    db,
                    caregiver.id,
                    tenant.id,
                    run.period_start,
                )
            return USStatutoryPayrollService.compute_for_caregiver(
                gross=gross,
                caregiver=caregiver,
                tenant=tenant,
                run=run,
                ytd_gross_before=ytd,
                db=db,
            )

        cfg = cls._config(tenant)
        if not cfg.get("statutory_enabled", True):
            return []

        profile = cls._caregiver_profile(caregiver)
        days = cls._period_days(run.period_start, run.period_end)
        deductions: list[dict] = []

        if cls._applicable(profile, "pf_applicable"):
            ceiling = cls._prorate_monthly(
                float(cfg["pf_wage_ceiling_monthly_inr"]),
                run.period_start,
                run.period_end,
            )
            pf_base = min(gross, ceiling)
            pf_rate = float(cfg["pf_employee_rate"])
            pf_amount = round(pf_base * pf_rate, 2)
            if pf_amount > 0:
                deductions.append(
                    {
                        "deduction_type": DEDUCTION_PF,
                        "base_amount": round(pf_base, 2),
                        "rate": pf_rate,
                        "amount": pf_amount,
                        "notes": f"Employee PF ({pf_rate * 100:.0f}% of wage base, {days}d period)",
                    }
                )

        if cls._applicable(profile, "esi_applicable"):
            esi_ceiling = cls._prorate_monthly(
                float(cfg["esi_gross_ceiling_monthly_inr"]),
                run.period_start,
                run.period_end,
            )
            if gross <= esi_ceiling:
                esi_rate = float(cfg["esi_employee_rate"])
                esi_amount = round(gross * esi_rate, 2)
                if esi_amount > 0:
                    deductions.append(
                        {
                            "deduction_type": DEDUCTION_ESI,
                            "base_amount": round(gross, 2),
                            "rate": esi_rate,
                            "amount": esi_amount,
                            "notes": f"Employee ESI ({esi_rate * 100:.2f}% of gross)",
                        }
                    )

        if cls._applicable(profile, "professional_tax_applicable"):
            pt_amount = cls._prorate_monthly(
                float(cfg["professional_tax_monthly_inr"]),
                run.period_start,
                run.period_end,
            )
            if pt_amount > 0:
                deductions.append(
                    {
                        "deduction_type": DEDUCTION_PT,
                        "base_amount": round(gross, 2),
                        "rate": None,
                        "amount": pt_amount,
                        "notes": "Professional tax (prorated monthly)",
                    }
                )

        if cls._applicable(profile, "tds_applicable"):
            threshold = float(cfg["tds_annual_threshold_inr"])
            tds_rate = float(cfg["tds_rate"])
            projected_fy = ytd_gross_before + gross
            if projected_fy > threshold:
                taxable = max(0.0, projected_fy - threshold)
                prior_taxable = max(0.0, ytd_gross_before - threshold)
                period_taxable = taxable - prior_taxable
                tds_amount = round(period_taxable * tds_rate, 2)
                if tds_amount > 0:
                    deductions.append(
                        {
                            "deduction_type": DEDUCTION_TDS,
                            "base_amount": round(period_taxable, 2),
                            "rate": tds_rate,
                            "amount": tds_amount,
                            "notes": (
                                f"TDS ({tds_rate * 100:.0f}% on FY taxable "
                                f"₹{period_taxable:,.0f})"
                            ),
                        }
                    )

        return deductions

    @classmethod
    def recompute_run(cls, db: Session, run: PayrollRun) -> dict:
        tenant = db.query(Tenant).filter(Tenant.id == run.tenant_id).first()
        if not tenant:
            return {"deductions": [], "total_deductions": 0.0, "total_net": run.total_amount}

        db.query(PayrollDeduction).filter(
            PayrollDeduction.payroll_run_id == run.id
        ).delete()

        lines = (
            db.query(PayrollLine)
            .filter(PayrollLine.payroll_run_id == run.id)
            .all()
        )
        if not lines:
            run.total_deductions = 0.0
            run.total_net = round(run.total_amount or 0.0, 2)
            return {"deductions": [], "total_deductions": 0.0, "total_net": run.total_net}

        cg_ids = {ln.caregiver_id for ln in lines}
        caregivers = {
            c.id: c
            for c in db.query(Caregiver).filter(Caregiver.id.in_(cg_ids)).all()
        }
        aggregated = FinanceOutputService.aggregate_payroll(lines, caregivers)

        all_rows: list[PayrollDeduction] = []
        for row in aggregated:
            cg = caregivers.get(row["caregiver_id"])
            if not cg:
                continue
            if tenant_market(tenant) == MARKET_US:
                from app.services.us_statutory_payroll_service import (
                    USStatutoryPayrollService,
                )

                ytd = USStatutoryPayrollService._ytd_gross(
                    db,
                    row["caregiver_id"],
                    run.tenant_id,
                    run.period_start,
                )
            else:
                ytd = cls._ytd_gross(
                    db,
                    row["caregiver_id"],
                    run.tenant_id,
                    run.period_start,
                )
            for item in cls.compute_for_caregiver(
                gross=row["gross"],
                caregiver=cg,
                tenant=tenant,
                run=run,
                ytd_gross_before=ytd,
                db=db,
            ):
                ded = PayrollDeduction(
                    payroll_run_id=run.id,
                    caregiver_id=row["caregiver_id"],
                    deduction_type=item["deduction_type"],
                    base_amount=item["base_amount"],
                    rate=item["rate"],
                    amount=item["amount"],
                    notes=item["notes"],
                )
                db.add(ded)
                all_rows.append(ded)

        total_deductions = round(sum(d.amount for d in all_rows), 2)
        run.total_deductions = total_deductions
        run.total_net = round((run.total_amount or 0.0) - total_deductions, 2)
        return {
            "deductions": all_rows,
            "total_deductions": total_deductions,
            "total_net": run.total_net,
        }

    @classmethod
    def deductions_for_run(cls, db: Session, run_id: int) -> list[PayrollDeduction]:
        return (
            db.query(PayrollDeduction)
            .filter(PayrollDeduction.payroll_run_id == run_id)
            .order_by(PayrollDeduction.caregiver_id, PayrollDeduction.deduction_type)
            .all()
        )

    @classmethod
    def summaries_for_run(
        cls,
        db: Session,
        run: PayrollRun,
        lines: list[PayrollLine],
        caregivers: dict[int, Caregiver],
    ) -> list[dict]:
        aggregated = FinanceOutputService.aggregate_payroll(lines, caregivers)
        deductions = cls.deductions_for_run(db, run.id)
        by_cg: dict[int, list[dict]] = {}
        for d in deductions:
            by_cg.setdefault(d.caregiver_id, []).append(
                {
                    "deduction_type": d.deduction_type,
                    "base_amount": d.base_amount,
                    "rate": d.rate,
                    "amount": d.amount,
                    "notes": d.notes,
                }
            )

        summaries = []
        for row in aggregated:
            deds = by_cg.get(row["caregiver_id"], [])
            total_ded = round(sum(x["amount"] for x in deds), 2)
            summaries.append(
                {
                    "caregiver_id": row["caregiver_id"],
                    "caregiver_name": row["caregiver_name"],
                    "hours": row["hours"],
                    "gross": row["gross"],
                    "deductions": deds,
                    "total_deductions": total_ded,
                    "net": round(row["gross"] - total_ded, 2),
                }
            )
        return summaries

    @classmethod
    def enrich_aggregated(
        cls,
        aggregated: list[dict],
        deductions: list[PayrollDeduction],
    ) -> list[dict]:
        by_cg: dict[int, list[dict]] = {}
        for d in deductions:
            by_cg.setdefault(d.caregiver_id, []).append(
                {
                    "deduction_type": d.deduction_type,
                    "amount": d.amount,
                    "notes": d.notes,
                }
            )
        for row in aggregated:
            deds = by_cg.get(row["caregiver_id"], [])
            row["deductions"] = deds
            row["total_deductions"] = round(sum(x["amount"] for x in deds), 2)
            row["net"] = round(row["gross"] - row["total_deductions"], 2)
        return aggregated

    @classmethod
    def statutory_register_csv(
        cls,
        *,
        run: PayrollRun,
        summaries: list[dict],
    ) -> str:
        import csv
        import io

        output = io.StringIO()
        writer = SafeWriter(output)
        writer.writerow(
            [
                "Caregiver ID",
                "Caregiver Name",
                "Hours",
                "Gross (INR)",
                "PF",
                "ESI",
                "Professional Tax",
                "TDS",
                "Total Deductions",
                "Net Pay (INR)",
            ]
        )
        for s in summaries:
            by_type = {d["deduction_type"]: d["amount"] for d in s["deductions"]}
            writer.writerow(
                [
                    s["caregiver_id"],
                    s["caregiver_name"],
                    f"{s['hours']:.2f}",
                    f"{s['gross']:.2f}",
                    f"{by_type.get(DEDUCTION_PF, 0):.2f}",
                    f"{by_type.get(DEDUCTION_ESI, 0):.2f}",
                    f"{by_type.get(DEDUCTION_PT, 0):.2f}",
                    f"{by_type.get(DEDUCTION_TDS, 0):.2f}",
                    f"{s['total_deductions']:.2f}",
                    f"{s['net']:.2f}",
                ]
            )
        writer.writerow(
            [
                "TOTAL",
                "",
                "",
                f"{run.total_amount:.2f}",
                "",
                "",
                "",
                "",
                f"{(run.total_deductions or 0):.2f}",
                f"{(run.total_net or run.total_amount):.2f}",
            ]
        )
        return output.getvalue()
