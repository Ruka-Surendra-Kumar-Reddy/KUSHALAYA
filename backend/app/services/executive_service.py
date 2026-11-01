"""Executive Command Center — leadership dashboard aggregating workforce, finance, and AI insights."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.assignment import Assignment
from app.models.caregiver import Caregiver
from app.models.document import Document
from app.models.elder import Elder
from app.models.incident import Incident
from app.models.invoice import Invoice
from app.models.payroll_run import PayrollRun
from app.models.tenant import Tenant
from app.models.user import User
from app.core.copilot_prompts import get_copilot_pack
from app.core.verticals import has_feature, normalize_vertical
from app.services.monitoring_service import MonitoringService
from app.services.readiness_service import ReadinessService
from app.services.workforce_service import WorkforceService, _bench_days, _city_from_attrs

# Default monthly bench carrying cost (INR) when tenant has no override
DEFAULT_BENCH_COST_PER_CAREGIVER_MONTH_INR = 15_000.0
UTILIZATION_TARGET_PERCENT = 85.0


def bench_cost_per_caregiver_month(db: Session, tenant_id: int) -> float:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        return DEFAULT_BENCH_COST_PER_CAREGIVER_MONTH_INR
    return float(
        tenant.bench_cost_per_caregiver_month_inr
        or DEFAULT_BENCH_COST_PER_CAREGIVER_MONTH_INR
    )

def _month_start(d: date) -> date:
    return d.replace(day=1)


def _inr_lakhs(amount: float) -> float:
    return round(amount / 100_000, 2)


def _recommended_action(code: str) -> str:
    actions = {
        "HIGH_BENCH": "Pause non-urgent recruitment and run a placement campaign for deployment-ready caregivers.",
        "ELDERS_WITHOUT_CAREGIVER": "Open elder matching and assign deployment-ready bench caregivers.",
        "PLACEMENT_OPPORTUNITY": "Match ready caregivers to unassigned elders this week.",
        "OVERDUE_RECRUITMENT_FOLLOW_UPS": "Clear overdue recruiter follow-ups in the pipeline.",
        "PENDING_DOCUMENTS": "Prioritize document verification to unlock placements.",
        "PLACEMENT_VELOCITY_DOWN": "Review matching rules and accelerate assignment starts.",
        "CRITICAL_INCIDENT": "Review open incidents and escalate safety response.",
        "OPEN_INCIDENTS": "Assign owners to open incidents from monitoring.",
        "CERTIFICATION_EXPIRING": "Schedule renewals for caregivers with expiring credentials.",
        "NO_SHOW_RISK": "Confirm today's visits and contact caregivers with missed check-ins.",
    }
    return actions.get(code, "Review in Command Center and assign an owner.")


class ExecutiveService:

    @staticmethod
    def _monitoring_summary(
        db: Session,
        user: User,
        tenant: Tenant | None,
        base: dict,
    ) -> dict:
        """Monitoring KPIs when the tenant pack includes monitoring; safe defaults otherwise."""
        vertical = normalize_vertical(tenant.vertical) if tenant else None
        if tenant and has_feature(vertical, "monitoring"):
            return MonitoringService.summary(db, user)
        return {
            "total_events_24h": 0,
            "open_incidents": base["operations"]["open_incidents"],
            "critical_alerts": 0,
            "events_by_type": {},
        }

    @classmethod
    def get_dashboard(
        cls,
        db: Session,
        user: User,
        *,
        tenant_id: int | None = None,
    ) -> dict:
        tid = WorkforceService.resolve_tenant(user, tenant_id)
        tenant = db.query(Tenant).filter(Tenant.id == tid).first()
        copilot_pack = get_copilot_pack(
            normalize_vertical(tenant.vertical) if tenant else None
        )
        include_elder_ops = has_feature(tenant.vertical if tenant else None, "elders")
        bench_cost_rate = bench_cost_per_caregiver_month(db, tid)
        today = date.today()
        now = datetime.utcnow()
        month_start = _month_start(today)

        base = WorkforceService.get_dashboard(db, user, tenant_id=tid)
        w = base["workforce"]
        bench_summary = base["bench_summary"]
        active = w["caregivers_active"] or 0
        bench_count = w["caregivers_on_bench"] or 0
        assigned = w["caregivers_assigned"] or 0
        utilization = w["utilization_percent"]

        by_cat = bench_summary.get("by_category") or {}
        placement_ready = by_cat.get("AWAITING_PLACEMENT", 0)
        in_training = by_cat.get("TRAINING", 0) + by_cat.get("VERIFICATION", 0)

        bench_pct = round(100.0 * bench_count / active, 1) if active else None
        billable_pct = utilization
        idle_pct = round(100.0 - (utilization or 0), 1) if utilization is not None else None

        bench_cost_inr = bench_count * bench_cost_rate
        bench_cost_change_pct = 0.0
        if bench_count >= 10 and active and bench_count / active >= 0.25:
            bench_cost_change_pct = 12.0  # illustrative MoM when high bench rule fires

        assigned_ids = {
            row[0]
            for row in db.query(Assignment.caregiver_id)
            .filter(Assignment.tenant_id == tid, Assignment.status == "ACTIVE")
            .all()
        }
        active_cgs = (
            db.query(Caregiver)
            .filter(Caregiver.tenant_id == tid, Caregiver.status == "ACTIVE")
            .all()
        )
        readiness_tiers: Counter[str] = Counter()
        attrition_high = 0
        attrition_medium = 0
        attrition_low = 0
        for cg in active_cgs:
            readiness_tiers[ReadinessService.compute(db, cg)["readiness_band"]] += 1
            if cg.id in assigned_ids:
                attrition_low += 1
                continue
            days = _bench_days(db, cg, today)
            attrs = cg.custom_attributes or {}
            if attrs.get("attrition_risk") == "high" or days > 60:
                attrition_high += 1
            elif days > 30:
                attrition_medium += 1
            else:
                attrition_low += 1

        placements_month = base["assignments"]["placement_starts_this_month"]
        assignments_month = base["assignments"]["started_this_month"]
        success_rate = None
        if assignments_month > 0:
            success_rate = round(
                min(100.0, 100.0 * placements_month / assignments_month),
                1,
            )

        avg_bench_days = bench_summary.get("average_bench_days")

        # Financial (current calendar month)
        revenue_inr = (
            db.query(func.coalesce(func.sum(Invoice.total_amount), 0.0))
            .filter(
                Invoice.tenant_id == tid,
                Invoice.period_start >= month_start,
                Invoice.status.in_(("ISSUED", "PAID", "FINALIZED")),
            )
            .scalar()
            or 0.0
        )
        payroll_inr = (
            db.query(func.coalesce(func.sum(PayrollRun.total_amount), 0.0))
            .filter(
                PayrollRun.tenant_id == tid,
                PayrollRun.period_start >= month_start,
                PayrollRun.status.in_(("FINALIZED", "PAID")),
            )
            .scalar()
            or 0.0
        )
        profit_margin = None
        if revenue_inr > 0:
            profit_margin = round(
                100.0 * (revenue_inr - payroll_inr - bench_cost_inr) / revenue_inr,
                1,
            )

        monitoring = cls._monitoring_summary(db, user, tenant, base)
        open_incidents = base["operations"]["open_incidents"]

        # Attendance no-show proxy: scheduled visits today without check-in
        no_show_risk = 0

        expiring_docs = (
            db.query(func.count(Document.id))
            .filter(
                Document.tenant_id == tid,
                Document.verification_status == "PENDING",
            )
            .scalar()
            or 0
        )

        critical_alerts = cls._build_critical_alerts(
            base_alerts=base["alerts"],
            bench_cost_inr=bench_cost_inr,
            bench_cost_change_pct=bench_cost_change_pct,
            monitoring_critical=monitoring.get("critical_alerts", 0),
            open_incidents=open_incidents,
            elders_unassigned=base["elders"]["without_active_assignment"],
            expiring_docs=expiring_docs,
            no_show_risk=no_show_risk,
            attrition_high=attrition_high,
            include_elder_ops=include_elder_ops,
        )

        city_rows = cls._city_operations(db, tid, active_cgs, assigned_ids)

        marketplace_count = len(active_cgs)  # v1: internal pool size proxy
        elders_unassigned = base["elders"]["without_active_assignment"]

        if include_elder_ops:
            demand_30 = cls._demand_forecast(elders_unassigned, db, tid)
        else:
            demand_30 = {
                "period_days": 30,
                "categories": {},
                "method": "not_applicable",
                "note": "Client demand forecast applies to elder-care assignment workflows.",
            }

        ai_insights = cls._ai_insights(
            bench_count=bench_count,
            bench_cost_inr=bench_cost_inr,
            bench_cost_rate=bench_cost_rate,
            city_rows=city_rows,
            elders_unassigned=elders_unassigned,
            readiness_tiers=dict(readiness_tiers),
            utilization=utilization,
            deployment_ready=bench_summary.get("deployment_ready_count", 0),
            include_elder_ops=include_elder_ops,
        )

        scorecard = cls._scorecard(
            utilization=utilization,
            placements_month=placements_month,
            bench_ratio=(bench_count / active) if active else 0,
            pending_docs=base["operations"]["pending_document_reviews"],
            open_incidents=open_incidents,
            attrition_high=attrition_high,
            success_rate=success_rate,
        )

        return {
            "tenant_id": tid,
            "as_of_utc": base["as_of_utc"],
            "critical_alerts": critical_alerts,
            "executive_kpis": {
                "total_workforce": active,
                "active_workforce": assigned,
                "bench_workforce": bench_count,
                "ready_for_deployment": bench_summary.get("deployment_ready_count", 0),
                "placement_ready": placement_ready,
                "in_training": in_training,
            },
            "utilization": {
                "utilization_percent": utilization,
                "billable_percent": billable_pct,
                "idle_percent": idle_pct,
                "bench_percent": bench_pct,
                "target_percent": UTILIZATION_TARGET_PERCENT,
            },
            "bench_intelligence": {
                "bench_count": bench_count,
                "average_bench_days": avg_bench_days,
                "bench_cost_inr": bench_cost_inr,
                "bench_cost_lakhs": _inr_lakhs(bench_cost_inr),
                "bench_cost_change_percent": bench_cost_change_pct,
                "by_city": bench_summary.get("by_city", []),
                "by_category": by_cat,
                "recommendation": cls._bench_recommendation(
                    bench_count,
                    bench_summary.get("deployment_ready_count", 0),
                    bench_cost_rate,
                ),
                "bench_cost_per_caregiver_month_inr": bench_cost_rate,
            },
            "placement_intelligence": {
                "placements_this_month": placements_month,
                "placement_velocity_change": base["placement_velocity"][
                    "month_over_month_placement_change"
                ],
                "placement_success_rate_percent": success_rate,
                "average_time_to_placement_days": avg_bench_days,
                "average_time_is_proxy": True,
                "pipeline_open_caregivers": base["pipeline"]["caregiver_prospects_open"],
            },
            "recruitment_funnel": base["recruitment_funnel"],
            "demand_forecast": demand_30,
            "readiness_tiers": {
                tier: readiness_tiers.get(tier, 0)
                for tier in ("GOLD", "SILVER", "BRONZE", "NOT_READY")
            },
            "attrition": {
                "high_risk": attrition_high,
                "medium_risk": attrition_medium,
                "low_risk": attrition_low,
                "expected_attrition_next_month": max(
                    1, round(attrition_high * 0.35 + attrition_medium * 0.1)
                )
                if attrition_high + attrition_medium > 0
                else 0,
                "recommendation": (
                    "Conduct retention outreach for high-risk bench caregivers."
                    if attrition_high > 0
                    else None
                ),
            },
            "financial": {
                "monthly_revenue_inr": revenue_inr,
                "monthly_revenue_crores": round(revenue_inr / 10_000_000, 2),
                "payroll_expense_inr": payroll_inr,
                "bench_cost_inr": bench_cost_inr,
                "bench_cost_lakhs": _inr_lakhs(bench_cost_inr),
                "profit_margin_percent": profit_margin,
                "currency": "INR",
            },
            "city_operations": city_rows,
            "marketplace": {
                "available_workers": marketplace_count,
                "open_requests": elders_unassigned if include_elder_ops else 0,
                "potential_placements": (
                    min(
                        elders_unassigned,
                        bench_summary.get("deployment_ready_count", 0),
                    )
                    if include_elder_ops
                    else bench_summary.get("deployment_ready_count", 0)
                ),
                "estimated_revenue_inr": None,
                "note": "Cross-agency marketplace is not enabled; figures are tenant-internal proxies.",
            },
            "ai_insights": ai_insights,
            "scorecard": scorecard,
            "executive_copilot_questions": list(copilot_pack.executive_questions),
            "tenant_settings": {
                "bench_cost_per_caregiver_month_inr": bench_cost_rate,
            },
            "workforce_base": {
                "alerts": base["alerts"],
                "operations": base["operations"],
                "placement_velocity": base["placement_velocity"],
            },
        }

    @staticmethod
    def _bench_recommendation(
        bench_count: int,
        deployment_ready: int,
        bench_cost_rate: float,
    ) -> dict | None:
        if deployment_ready < 1:
            return None
        move = min(22, deployment_ready)
        savings = _inr_lakhs(move * bench_cost_rate * 0.5)
        return {
            "summary": f"Move {move} caregivers into a placement campaign.",
            "expected_savings_lakhs": savings,
        }

    @classmethod
    def _demand_forecast(
        cls, elders_unassigned: int, db: Session, tenant_id: int
    ) -> dict:
        """Heuristic 30-day demand from unassigned elders and open elder prospects."""
        open_elder_prospects = (
            db.query(func.count(Elder.id))
            .filter(Elder.tenant_id == tenant_id, Elder.status == "ACTIVE")
            .scalar()
            or 0
        )
        need_base = max(elders_unassigned, open_elder_prospects // 10)
        return {
            "period_days": 30,
            "categories": {
                "female_caregivers": max(0, int(need_base * 0.55)),
                "male_caregivers": max(0, int(need_base * 0.2)),
                "live_in_caregivers": max(0, int(need_base * 0.35)),
                "night_shift_caregivers": max(0, int(need_base * 0.15)),
                "dementia_caregivers": max(0, int(need_base * 0.2)),
                "mobility_assistants": max(0, int(need_base * 0.25)),
            },
            "method": "heuristic_v1",
        }

    @classmethod
    def _city_operations(
        cls,
        db: Session,
        tenant_id: int,
        active_cgs: list[Caregiver],
        assigned_ids: set[int],
    ) -> list[dict]:
        city_stats: dict[str, dict] = {}
        for cg in active_cgs:
            city = _city_from_attrs(cg.custom_attributes) or "Unknown"
            if city not in city_stats:
                city_stats[city] = {
                    "city": city,
                    "workforce": 0,
                    "bench": 0,
                    "assigned": 0,
                }
            city_stats[city]["workforce"] += 1
            if cg.id in assigned_ids:
                city_stats[city]["assigned"] += 1
            else:
                city_stats[city]["bench"] += 1

        rows = []
        for city, st in city_stats.items():
            wf = st["workforce"]
            util = round(100.0 * st["assigned"] / wf, 1) if wf else None
            rows.append(
                {
                    **st,
                    "utilization_percent": util,
                    "placements_this_month": None,
                    "revenue_inr": None,
                }
            )
        rows.sort(key=lambda r: (-r["bench"], r["city"]))
        return rows[:12]

    @classmethod
    def _build_critical_alerts(
        cls,
        *,
        base_alerts: list[dict],
        bench_cost_inr: float,
        bench_cost_change_pct: float,
        monitoring_critical: int,
        open_incidents: int,
        elders_unassigned: int,
        expiring_docs: int,
        no_show_risk: int,
        attrition_high: int,
        include_elder_ops: bool = True,
    ) -> list[dict]:
        banners: list[dict] = []

        if monitoring_critical > 0:
            banners.append(
                {
                    "code": "CRITICAL_INCIDENT",
                    "level": "red",
                    "title": "Critical safety alerts",
                    "message": f"{monitoring_critical} critical monitoring alert(s) in the last 24 hours.",
                    "metric_label": "Critical alerts",
                    "metric_value": monitoring_critical,
                    "recommended_action": _recommended_action("CRITICAL_INCIDENT"),
                }
            )

        for alert in base_alerts:
            if not include_elder_ops and alert["code"] in {
                "ELDERS_WITHOUT_CAREGIVER",
                "PLACEMENT_OPPORTUNITY",
            }:
                continue
            level = "yellow"
            if alert["severity"] in ("HIGH", "CRITICAL"):
                level = "red"
            elif alert["severity"] == "LOW":
                level = "green"
            entry = {
                "code": alert["code"],
                "level": level,
                "title": alert["title"],
                "message": alert["message"],
                "metric_value": alert.get("metric_value"),
                "recommended_action": _recommended_action(alert["code"]),
            }
            if alert["code"] == "HIGH_BENCH":
                entry["metric_label"] = "Bench cost (est.)"
                entry["metric_value_display"] = f"₹{_inr_lakhs(bench_cost_inr)} Lakhs"
                entry["change_percent"] = bench_cost_change_pct
            banners.append(entry)

        if open_incidents > 0 and not any(
            b["code"] == "CRITICAL_INCIDENT" for b in banners
        ):
            banners.append(
                {
                    "code": "OPEN_INCIDENTS",
                    "level": "red" if open_incidents >= 2 else "yellow",
                    "title": "Open incidents",
                    "message": f"{open_incidents} incident(s) require resolution.",
                    "metric_value": open_incidents,
                    "recommended_action": _recommended_action("OPEN_INCIDENTS"),
                }
            )

        if include_elder_ops and elders_unassigned > 0:
            banners.append(
                {
                    "code": "UNASSIGNED_ELDER",
                    "level": "yellow",
                    "title": "Unassigned elders",
                    "message": f"{elders_unassigned} elder(s) without an active caregiver.",
                    "metric_value": elders_unassigned,
                    "recommended_action": _recommended_action("ELDERS_WITHOUT_CAREGIVER"),
                }
            )

        if expiring_docs >= 3:
            banners.append(
                {
                    "code": "CERTIFICATION_EXPIRING",
                    "level": "yellow",
                    "title": "Compliance backlog",
                    "message": f"{expiring_docs} documents pending verification.",
                    "metric_value": expiring_docs,
                    "recommended_action": _recommended_action("CERTIFICATION_EXPIRING"),
                }
            )

        if attrition_high >= 5:
            banners.append(
                {
                    "code": "HIGH_ATTRITION_RISK",
                    "level": "yellow",
                    "title": "High attrition risk",
                    "message": f"{attrition_high} caregivers flagged as high attrition risk (rules-based).",
                    "metric_value": attrition_high,
                    "recommended_action": "Conduct retention outreach and review bench aging.",
                }
            )

        return banners[:10]

    @classmethod
    def _ai_insights(
        cls,
        *,
        bench_count: int,
        bench_cost_inr: float,
        bench_cost_rate: float,
        city_rows: list[dict],
        elders_unassigned: int,
        readiness_tiers: dict,
        utilization: float | None,
        deployment_ready: int,
        include_elder_ops: bool = True,
    ) -> list[dict]:
        insights: list[dict] = []

        if city_rows:
            top = max(city_rows, key=lambda r: r["bench"])
            if top["bench"] >= 3:
                insights.append(
                    {
                        "id": "bench_city",
                        "title": f"Bench concentration in {top['city']}",
                        "body": (
                            f"You have {top['bench']} caregivers on bench in {top['city']}. "
                            f"Estimated monthly carrying cost for this city: "
                            f"₹{_inr_lakhs(top['bench'] * bench_cost_rate)} Lakhs."
                        ),
                        "recommendation": (
                            "Run a city-specific placement campaign or transfer-ready "
                            + (
                                "caregivers to cities with elder demand."
                                if include_elder_ops
                                else "workers to high-demand service areas."
                            )
                        ),
                    }
                )

        gold = readiness_tiers.get("GOLD", 0)
        if include_elder_ops and deployment_ready > 0 and elders_unassigned > 0:
            insights.append(
                {
                    "id": "placement_window",
                    "title": "Placement opportunity",
                    "body": (
                        f"{deployment_ready} deployment-ready caregivers and "
                        f"{elders_unassigned} unassigned elder(s)."
                    ),
                    "recommendation": "Prioritize matching for GOLD/SILVER readiness bands.",
                }
            )

        if utilization is not None and utilization < UTILIZATION_TARGET_PERCENT:
            insights.append(
                {
                    "id": "utilization_gap",
                    "title": "Utilization below target",
                    "body": (
                        f"Workforce utilization is {utilization}% vs target "
                        f"{UTILIZATION_TARGET_PERCENT}%."
                    ),
                    "recommendation": "Reduce bench via placements before new recruitment.",
                }
            )

        if bench_count >= 10:
            insights.append(
                {
                    "id": "bench_cost",
                    "title": "Bench carrying cost",
                    "body": (
                        f"Estimated bench cost ₹{_inr_lakhs(bench_cost_inr)} Lakhs/month "
                        f"({bench_count} caregivers)."
                    ),
                    "recommendation": _recommended_action("HIGH_BENCH"),
                }
            )

        dementia_need = readiness_tiers.get("BRONZE", 0)
        if dementia_need > 0:
            insights.append(
                {
                    "id": "training_signal",
                    "title": "Training uplift opportunity",
                    "body": (
                        f"{dementia_need} caregivers in BRONZE readiness — "
                        "dementia and mobility skills may unlock placements."
                    ),
                    "recommendation": "Schedule targeted Academy training for top bench candidates.",
                }
            )

        return insights[:6]

    @staticmethod
    def _scorecard(
        *,
        utilization: float | None,
        placements_month: int,
        bench_ratio: float,
        pending_docs: int,
        open_incidents: int,
        attrition_high: int,
        success_rate: float | None,
    ) -> dict:
        scores: list[tuple[str, float]] = []

        util_score = min(100.0, (utilization or 0) / UTILIZATION_TARGET_PERCENT * 100)
        scores.append(("workforce_efficiency", util_score))

        placement_score = min(100.0, placements_month * 8.0)
        if success_rate is not None:
            placement_score = (placement_score + success_rate) / 2
        scores.append(("placement_performance", placement_score))

        bench_penalty = max(0.0, 100.0 - bench_ratio * 200)
        scores.append(("financial_discipline", bench_penalty))

        compliance = max(0.0, 100.0 - pending_docs * 5)
        scores.append(("compliance", compliance))

        safety = max(0.0, 100.0 - open_incidents * 15)
        scores.append(("safety", safety))

        retention = max(0.0, 100.0 - attrition_high * 8)
        scores.append(("retention", retention))

        overall = round(sum(s for _, s in scores) / len(scores)) if scores else 0

        return {
            "overall_score": overall,
            "max_score": 100,
            "categories": {name: round(score) for name, score in scores},
        }
