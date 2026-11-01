"""US payroll deductions — FICA (Social Security + Medicare) and simplified federal withholding."""

from __future__ import annotations

from datetime import date

from app.models.caregiver import Caregiver
from app.models.payroll_run import PayrollRun
from app.models.tenant import Tenant

DEDUCTION_FICA_SS = "FICA_SS"
DEDUCTION_FICA_MEDICARE = "FICA_MEDICARE"
DEDUCTION_FEDERAL_WH = "FEDERAL_WITHHOLDING"

DEFAULT_US_PAYROLL_CONFIG = {
    "statutory_enabled": True,
    "fica_ss_rate": 0.062,
    "fica_ss_wage_base_annual_usd": 168_600.0,
    "fica_medicare_rate": 0.0145,
    "federal_withholding_rate": 0.12,
    "federal_withholding_annual_exemption_usd": 14_600.0,
}


class USStatutoryPayrollService:

    @staticmethod
    def _config(tenant: Tenant) -> dict:
        raw = getattr(tenant, "payroll_config", None) or {}
        return {**DEFAULT_US_PAYROLL_CONFIG, **raw}

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
    def _period_days(period_start: date, period_end: date) -> int:
        return (period_end - period_start).days + 1

    @staticmethod
    def _calendar_year_start(for_date: date) -> date:
        return date(for_date.year, 1, 1)

    @classmethod
    def _ytd_gross(
        cls,
        db,
        caregiver_id: int,
        tenant_id: int,
        before_period_start: date,
    ) -> float:
        from app.models.payroll_run import PayrollLine, PayrollRun

        year_start = cls._calendar_year_start(before_period_start)
        rows = (
            db.query(PayrollLine.amount)
            .join(PayrollRun, PayrollRun.id == PayrollLine.payroll_run_id)
            .filter(
                PayrollLine.caregiver_id == caregiver_id,
                PayrollRun.tenant_id == tenant_id,
                PayrollRun.status == "FINALIZED",
                PayrollRun.period_end >= year_start,
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
        db=None,
    ) -> list[dict]:
        cfg = cls._config(tenant)
        if not cfg.get("statutory_enabled", True):
            return []

        profile = cls._caregiver_profile(caregiver)
        deductions: list[dict] = []
        days = cls._period_days(run.period_start, run.period_end)
        period_fraction = days / 365.0

        if cls._applicable(profile, "fica_ss_applicable"):
            wage_base = float(cfg["fica_ss_wage_base_annual_usd"]) * period_fraction
            remaining_base = max(0.0, wage_base - ytd_gross_before)
            ss_base = min(gross, remaining_base)
            ss_rate = float(cfg["fica_ss_rate"])
            ss_amount = round(ss_base * ss_rate, 2)
            if ss_amount > 0:
                deductions.append(
                    {
                        "deduction_type": DEDUCTION_FICA_SS,
                        "base_amount": round(ss_base, 2),
                        "rate": ss_rate,
                        "amount": ss_amount,
                        "notes": f"Social Security ({ss_rate * 100:.1f}% employee)",
                    }
                )

        if cls._applicable(profile, "fica_medicare_applicable"):
            med_rate = float(cfg["fica_medicare_rate"])
            med_amount = round(gross * med_rate, 2)
            if med_amount > 0:
                deductions.append(
                    {
                        "deduction_type": DEDUCTION_FICA_MEDICARE,
                        "base_amount": round(gross, 2),
                        "rate": med_rate,
                        "amount": med_amount,
                        "notes": f"Medicare ({med_rate * 100:.2f}% employee)",
                    }
                )

        if cls._applicable(profile, "federal_withholding_applicable"):
            exemption = float(cfg["federal_withholding_annual_exemption_usd"])
            wh_rate = float(cfg["federal_withholding_rate"])
            projected_ytd = ytd_gross_before + gross
            if projected_ytd > exemption:
                taxable_ytd = max(0.0, projected_ytd - exemption)
                prior_taxable = max(0.0, ytd_gross_before - exemption)
                period_taxable = taxable_ytd - prior_taxable
                wh_amount = round(period_taxable * wh_rate, 2)
                if wh_amount > 0:
                    deductions.append(
                        {
                            "deduction_type": DEDUCTION_FEDERAL_WH,
                            "base_amount": round(period_taxable, 2),
                            "rate": wh_rate,
                            "amount": wh_amount,
                            "notes": (
                                f"Federal withholding ({wh_rate * 100:.0f}% "
                                f"on taxable wages)"
                            ),
                        }
                    )

        return deductions
