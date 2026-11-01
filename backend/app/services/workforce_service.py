"""Workforce Operations Suite — bench inventory and command center dashboard."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.pipeline_constants import CAREGIVER_PROSPECT_STAGES, PROSPECT_STATUS_OPEN
from app.core.rbac import resolve_tenant_id
from app.models.assignment import Assignment
from app.models.attendance_record import AttendanceRecord
from app.models.caregiver import Caregiver
from app.models.caregiver_prospect import CaregiverProspect
from app.models.caregiver_skill import CaregiverSkill
from app.models.document import Document
from app.models.elder import Elder
from app.models.elder_prospect import ElderProspect
from app.models.incident import Incident
from app.models.match_run import MatchRun
from app.models.placement_history import PlacementHistory
from app.models.skill import Skill
from app.models.user import User
from app.models.visit import Visit
from app.services.readiness_service import ReadinessService

BENCH_CATEGORIES = (
    "READY",
    "AWAITING_PLACEMENT",
    "VERIFICATION",
    "TRAINING",
    "RESTRICTED",
)


def _city_from_attrs(attrs: dict | None) -> str | None:
    if not attrs:
        return None
    addr = attrs.get("address") or attrs.get("city")
    if not addr or not isinstance(addr, str):
        return None
    text = addr.strip()
    if not text:
        return None
    if "," in text:
        return text.split(",")[-1].strip()[:80] or text[:80]
    return text[:80]


def _languages_from_attrs(attrs: dict | None) -> list[str]:
    if not attrs:
        return []
    langs = attrs.get("languages")
    if isinstance(langs, list):
        return [str(x) for x in langs if x][:10]
    return []


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _bench_category(caregiver: Caregiver, readiness: dict) -> str:
    attrs = caregiver.custom_attributes or {}
    if attrs.get("bench_restricted") or attrs.get("restricted"):
        return "RESTRICTED"
    if (caregiver.background_check_status or "").upper() in (
        "FAILED",
        "REJECTED",
        "SUSPENDED",
    ):
        return "RESTRICTED"

    score = readiness["readiness_score"]
    verification = readiness["breakdown"]["verification"]

    if score >= 90:
        return "READY"
    if score >= 75:
        return "AWAITING_PLACEMENT"
    if verification < 15:
        return "VERIFICATION"
    return "TRAINING"


def _bench_days(db: Session, caregiver: Caregiver, today: date) -> int:
    last_end = (
        db.query(func.max(Assignment.end_date))
        .filter(
            Assignment.caregiver_id == caregiver.id,
            Assignment.end_date.isnot(None),
        )
        .scalar()
    )
    anchor = last_end
    if anchor is None and caregiver.created_at:
        anchor = caregiver.created_at.date()
    if anchor is None:
        return 0
    return max(0, (today - anchor).days)


class WorkforceService:

    @staticmethod
    def resolve_tenant(user: User, tenant_id: int | None) -> int:
        tid = resolve_tenant_id(user, tenant_id)
        if tid is None:
            raise HTTPException(
                status_code=400,
                detail="tenant_id is required for platform administrators",
            )
        return tid

    @staticmethod
    def _active_bench(
        db: Session, tenant_id: int
    ) -> tuple[list[Caregiver], set[int], list[Caregiver]]:
        active = (
            db.query(Caregiver)
            .filter(Caregiver.tenant_id == tenant_id, Caregiver.status == "ACTIVE")
            .all()
        )
        assigned_ids = {
            row[0]
            for row in db.query(Assignment.caregiver_id)
            .filter(
                Assignment.tenant_id == tenant_id,
                Assignment.status == "ACTIVE",
            )
            .all()
        }
        bench = [c for c in active if c.id not in assigned_ids]
        return active, assigned_ids, bench

    @staticmethod
    def _skills_map(db: Session, caregiver_ids: list[int]) -> dict[int, list[str]]:
        if not caregiver_ids:
            return {}
        rows = (
            db.query(CaregiverSkill, Skill)
            .join(Skill, Skill.id == CaregiverSkill.skill_id)
            .filter(CaregiverSkill.caregiver_id.in_(caregiver_ids))
            .all()
        )
        out: dict[int, list[str]] = {}
        for cs, skill in rows:
            out.setdefault(cs.caregiver_id, []).append(skill.name or skill.code)
        return out

    @classmethod
    def build_bench_metrics(
        cls,
        db: Session,
        tenant_id: int,
        rows: list[dict],
    ) -> dict:
        by_cat: Counter[str] = Counter()
        by_city: Counter[str] = Counter()
        by_lang: Counter[str] = Counter()
        bench_days_list: list[int] = []
        deployment_ready = 0

        for row in rows:
            by_cat[row["category"]] += 1
            if row.get("city"):
                by_city[row["city"]] += 1
            for lang in row.get("languages") or []:
                by_lang[lang] += 1
            bench_days_list.append(row["bench_days"])
            if row["readiness_score"] >= 90:
                deployment_ready += 1

        avg_days = None
        if bench_days_list:
            avg_days = round(sum(bench_days_list) / len(bench_days_list), 1)

        return {
            "total_bench": len(rows),
            "by_category": {k: by_cat[k] for k in BENCH_CATEGORIES if by_cat[k]},
            "by_city": [
                {"city": c, "count": n} for c, n in by_city.most_common(12)
            ],
            "by_language": [
                {"language": lang, "count": n} for lang, n in by_lang.most_common(12)
            ],
            "average_bench_days": avg_days,
            "deployment_ready_count": deployment_ready,
        }

    @classmethod
    def get_bench(
        cls,
        db: Session,
        user: User,
        *,
        tenant_id: int | None = None,
        category: str | None = None,
    ) -> dict:
        tid = cls.resolve_tenant(user, tenant_id)
        today = date.today()
        now = datetime.utcnow()
        _, _, bench = cls._active_bench(db, tid)
        skill_map = cls._skills_map(db, [c.id for c in bench])

        rows: list[dict] = []
        for cg in bench:
            readiness = ReadinessService.compute(db, cg)
            cat = _bench_category(cg, readiness)
            if category and cat.upper() != category.upper():
                continue
            rows.append(
                {
                    "caregiver_id": cg.id,
                    "name": f"{cg.first_name} {cg.last_name}".strip(),
                    "category": cat,
                    "readiness_score": readiness["readiness_score"],
                    "readiness_band": readiness["readiness_band"],
                    "bench_days": _bench_days(db, cg, today),
                    "city": _city_from_attrs(cg.custom_attributes),
                    "languages": _languages_from_attrs(cg.custom_attributes),
                    "skills": skill_map.get(cg.id, [])[:8],
                    "top_gaps": readiness["recommendations"][:3],
                }
            )

        rows.sort(
            key=lambda r: (-r["readiness_score"], -r["bench_days"], r["name"]),
        )
        metrics = cls.build_bench_metrics(db, tid, rows)

        return {
            "tenant_id": tid,
            "as_of_utc": now.isoformat() + "Z",
            "metrics": metrics,
            "caregivers": rows,
        }

    @classmethod
    def _recruitment_funnel(cls, db: Session, tenant_id: int) -> list[dict]:
        counts: Counter[str] = Counter()
        rows = (
            db.query(CaregiverProspect.stage, func.count(CaregiverProspect.id))
            .filter(
                CaregiverProspect.tenant_id == tenant_id,
                CaregiverProspect.status == PROSPECT_STATUS_OPEN,
            )
            .group_by(CaregiverProspect.stage)
            .all()
        )
        for stage, cnt in rows:
            counts[stage or "UNKNOWN"] = cnt
        return [
            {"stage": stage, "count": counts.get(stage, 0)}
            for stage in CAREGIVER_PROSPECT_STAGES
            if stage not in ("HIRED", "REJECTED")
        ]

    @classmethod
    def _build_alerts(
        cls,
        *,
        bench_count: int,
        active_count: int,
        utilization: float | None,
        elders_unassigned: int,
        deployment_ready: int,
        overdue_follow_ups: int,
        pending_docs: int,
        placements_this_month: int,
        placements_last_month: int,
    ) -> list[dict]:
        alerts: list[dict] = []

        if active_count and bench_count / active_count >= 0.25:
            alerts.append(
                {
                    "code": "HIGH_BENCH",
                    "severity": "HIGH",
                    "title": "High bench population",
                    "message": (
                        f"{bench_count} of {active_count} active caregivers are on bench "
                        f"({utilization or 0}% utilized)."
                    ),
                    "metric_value": bench_count,
                }
            )
        elif bench_count >= 10:
            alerts.append(
                {
                    "code": "HIGH_BENCH",
                    "severity": "MEDIUM",
                    "title": "Bench population",
                    "message": f"{bench_count} caregivers awaiting assignment.",
                    "metric_value": bench_count,
                }
            )

        if elders_unassigned > 0:
            sev = "HIGH" if elders_unassigned >= 3 else "MEDIUM"
            alerts.append(
                {
                    "code": "ELDERS_WITHOUT_CAREGIVER",
                    "severity": sev,
                    "title": "Elders need placement",
                    "message": (
                        f"{elders_unassigned} active elder(s) have no active assignment."
                    ),
                    "metric_value": elders_unassigned,
                }
            )

        if deployment_ready > 0 and elders_unassigned > 0:
            alerts.append(
                {
                    "code": "PLACEMENT_OPPORTUNITY",
                    "severity": "MEDIUM",
                    "title": "Placement opportunity",
                    "message": (
                        f"{deployment_ready} deployment-ready caregivers on bench; "
                        f"{elders_unassigned} elder(s) unassigned."
                    ),
                    "metric_value": deployment_ready,
                }
            )

        if overdue_follow_ups > 0:
            alerts.append(
                {
                    "code": "OVERDUE_RECRUITMENT_FOLLOW_UPS",
                    "severity": "MEDIUM",
                    "title": "Overdue recruiter follow-ups",
                    "message": f"{overdue_follow_ups} open recruit prospect(s) past follow-up date.",
                    "metric_value": overdue_follow_ups,
                }
            )

        if pending_docs >= 5:
            alerts.append(
                {
                    "code": "PENDING_DOCUMENTS",
                    "severity": "LOW",
                    "title": "Document review backlog",
                    "message": f"{pending_docs} documents pending verification.",
                    "metric_value": pending_docs,
                }
            )

        if (
            placements_last_month > 0
            and placements_this_month < placements_last_month * 0.8
        ):
            alerts.append(
                {
                    "code": "PLACEMENT_VELOCITY_DOWN",
                    "severity": "MEDIUM",
                    "title": "Placement velocity down",
                    "message": (
                        f"{placements_this_month} placement starts this month vs "
                        f"{placements_last_month} last month."
                    ),
                    "metric_value": placements_this_month,
                }
            )

        return alerts

    @classmethod
    def get_dashboard(
        cls,
        db: Session,
        user: User,
        *,
        tenant_id: int | None = None,
    ) -> dict:
        tid = cls.resolve_tenant(user, tenant_id)
        today = date.today()
        now = datetime.utcnow()
        month_start = _month_start(today)
        prev_month_end = month_start - timedelta(days=1)
        prev_month_start = _month_start(prev_month_end)
        day_start = datetime.combine(today, datetime.min.time())
        week_end = now + timedelta(days=7)

        active_caregivers, assigned_ids, bench = cls._active_bench(db, tid)
        active_elders = (
            db.query(Elder)
            .filter(Elder.tenant_id == tid, Elder.status == "ACTIVE")
            .count()
        )
        elder_ids_assigned = {
            row[0]
            for row in db.query(Assignment.elder_id)
            .filter(Assignment.tenant_id == tid, Assignment.status == "ACTIVE")
            .all()
        }
        if elder_ids_assigned:
            elders_unassigned = (
                db.query(func.count(Elder.id))
                .filter(
                    Elder.tenant_id == tid,
                    Elder.status == "ACTIVE",
                    ~Elder.id.in_(elder_ids_assigned),
                )
                .scalar()
                or 0
            )
        else:
            elders_unassigned = active_elders

        utilization = None
        if active_caregivers:
            utilization = round(100.0 * len(assigned_ids) / len(active_caregivers), 1)

        bench_data = cls.get_bench(db, user, tenant_id=tid)
        bench_metrics = bench_data["metrics"]

        assignments_this_month = (
            db.query(func.count(Assignment.id))
            .filter(
                Assignment.tenant_id == tid,
                Assignment.start_date.isnot(None),
                Assignment.start_date >= month_start,
                Assignment.start_date <= today,
            )
            .scalar()
            or 0
        )
        assignments_last_month = (
            db.query(func.count(Assignment.id))
            .filter(
                Assignment.tenant_id == tid,
                Assignment.start_date.isnot(None),
                Assignment.start_date >= prev_month_start,
                Assignment.start_date <= prev_month_end,
            )
            .scalar()
            or 0
        )
        placements_this_month = (
            db.query(func.count(PlacementHistory.id))
            .filter(
                PlacementHistory.tenant_id == tid,
                PlacementHistory.start_date.isnot(None),
                PlacementHistory.start_date >= month_start,
                PlacementHistory.start_date <= today,
            )
            .scalar()
            or 0
        )
        placements_last_month = (
            db.query(func.count(PlacementHistory.id))
            .filter(
                PlacementHistory.tenant_id == tid,
                PlacementHistory.start_date.isnot(None),
                PlacementHistory.start_date >= prev_month_start,
                PlacementHistory.start_date <= prev_month_end,
            )
            .scalar()
            or 0
        )

        overdue_follow_ups = (
            db.query(func.count(CaregiverProspect.id))
            .filter(
                CaregiverProspect.tenant_id == tid,
                CaregiverProspect.status == PROSPECT_STATUS_OPEN,
                CaregiverProspect.next_follow_up_at.isnot(None),
                CaregiverProspect.next_follow_up_at < now,
            )
            .scalar()
            or 0
        )

        alerts = cls._build_alerts(
            bench_count=len(bench),
            active_count=len(active_caregivers),
            utilization=utilization,
            elders_unassigned=elders_unassigned,
            deployment_ready=bench_metrics["deployment_ready_count"],
            overdue_follow_ups=overdue_follow_ups,
            pending_docs=(
                db.query(func.count(Document.id))
                .filter(
                    Document.tenant_id == tid,
                    Document.verification_status == "PENDING",
                )
                .scalar()
                or 0
            ),
            placements_this_month=placements_this_month,
            placements_last_month=placements_last_month,
        )

        return {
            "tenant_id": tid,
            "as_of_utc": now.isoformat() + "Z",
            "workforce": {
                "caregivers_active": len(active_caregivers),
                "caregivers_on_bench": len(bench),
                "caregivers_assigned": len(assigned_ids),
                "utilization_percent": utilization,
                "deployment_ready_on_bench": bench_metrics["deployment_ready_count"],
            },
            "elders": {
                "active": active_elders,
                "without_active_assignment": elders_unassigned,
            },
            "assignments": {
                "active": len(assigned_ids),
                "started_this_month": assignments_this_month,
                "started_last_month": assignments_last_month,
                "placement_starts_this_month": placements_this_month,
                "placement_starts_last_month": placements_last_month,
            },
            "pipeline": {
                "elder_prospects_open": (
                    db.query(func.count(ElderProspect.id))
                    .filter(
                        ElderProspect.tenant_id == tid,
                        ElderProspect.status == PROSPECT_STATUS_OPEN,
                    )
                    .scalar()
                    or 0
                ),
                "caregiver_prospects_open": (
                    db.query(func.count(CaregiverProspect.id))
                    .filter(
                        CaregiverProspect.tenant_id == tid,
                        CaregiverProspect.status == PROSPECT_STATUS_OPEN,
                    )
                    .scalar()
                    or 0
                ),
                "overdue_recruiter_follow_ups": overdue_follow_ups,
            },
            "operations": {
                "pending_document_reviews": (
                    db.query(func.count(Document.id))
                    .filter(
                        Document.tenant_id == tid,
                        Document.verification_status == "PENDING",
                    )
                    .scalar()
                    or 0
                ),
                "open_incidents": (
                    db.query(func.count(Incident.id))
                    .filter(Incident.tenant_id == tid, Incident.status == "OPEN")
                    .scalar()
                    or 0
                ),
                "attendance_check_ins_today": (
                    db.query(func.count(AttendanceRecord.id))
                    .filter(
                        AttendanceRecord.tenant_id == tid,
                        AttendanceRecord.checkin_time.isnot(None),
                        AttendanceRecord.checkin_time >= day_start,
                    )
                    .scalar()
                    or 0
                ),
                "visits_scheduled_next_7_days": (
                    db.query(func.count(Visit.id))
                    .filter(
                        Visit.tenant_id == tid,
                        Visit.scheduled_start.isnot(None),
                        Visit.scheduled_start >= now,
                        Visit.scheduled_start <= week_end,
                    )
                    .scalar()
                    or 0
                ),
                "matching_runs_last_30_days": (
                    db.query(func.count(MatchRun.id))
                    .filter(
                        MatchRun.tenant_id == tid,
                        MatchRun.created_at >= now - timedelta(days=30),
                    )
                    .scalar()
                    or 0
                ),
            },
            "placement_velocity": {
                "assignments_started_this_month": assignments_this_month,
                "assignments_started_last_month": assignments_last_month,
                "placement_starts_this_month": placements_this_month,
                "placement_starts_last_month": placements_last_month,
                "month_over_month_placement_change": (
                    placements_this_month - placements_last_month
                ),
            },
            "recruitment_funnel": cls._recruitment_funnel(db, tid),
            "alerts": alerts,
            "bench_summary": bench_metrics,
        }
