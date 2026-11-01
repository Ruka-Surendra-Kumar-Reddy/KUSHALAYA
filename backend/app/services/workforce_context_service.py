"""Aggregate tenant operational metrics for Workforce Copilot (grounded context)."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.assignment import Assignment
from app.models.attendance_record import AttendanceRecord
from app.models.caregiver import Caregiver
from app.models.caregiver_prospect import CaregiverProspect
from app.models.document import Document
from app.models.elder import Elder
from app.models.elder_prospect import ElderProspect
from app.models.incident import Incident
from app.models.match_run import MatchRun
from app.models.placement_history import PlacementHistory
from app.models.visit import Visit
from app.services.readiness_service import ReadinessService


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


def _month_start(d: date) -> date:
    return d.replace(day=1)


class WorkforceContextService:

    @staticmethod
    def build(db: Session, tenant_id: int) -> dict:
        today = date.today()
        now = datetime.utcnow()
        month_start = _month_start(today)
        prev_month_end = month_start - timedelta(days=1)
        prev_month_start = _month_start(prev_month_end)
        day_start = datetime.combine(today, datetime.min.time())
        week_end = now + timedelta(days=7)

        active_caregivers = (
            db.query(Caregiver)
            .filter(Caregiver.tenant_id == tenant_id, Caregiver.status == "ACTIVE")
            .all()
        )
        active_elders = (
            db.query(Elder)
            .filter(Elder.tenant_id == tenant_id, Elder.status == "ACTIVE")
            .all()
        )

        active_assignments = (
            db.query(Assignment)
            .filter(Assignment.tenant_id == tenant_id, Assignment.status == "ACTIVE")
            .all()
        )
        assigned_caregiver_ids = {a.caregiver_id for a in active_assignments}
        elder_ids_with_assignment = {a.elder_id for a in active_assignments}

        bench = [c for c in active_caregivers if c.id not in assigned_caregiver_ids]
        elders_needing_care = [
            e for e in active_elders if e.id not in elder_ids_with_assignment
        ]

        utilization_pct = None
        if active_caregivers:
            utilization_pct = round(
                100.0 * len(assigned_caregiver_ids) / len(active_caregivers),
                1,
            )

        # Assignments started this / last month (by start_date)
        def assignments_started_between(start: date, end: date) -> int:
            return (
                db.query(func.count(Assignment.id))
                .filter(
                    Assignment.tenant_id == tenant_id,
                    Assignment.start_date.isnot(None),
                    Assignment.start_date >= start,
                    Assignment.start_date <= end,
                )
                .scalar()
                or 0
            )

        assignments_this_month = assignments_started_between(month_start, today)
        assignments_last_month = assignments_started_between(
            prev_month_start, prev_month_end
        )

        placements_this_month = (
            db.query(func.count(PlacementHistory.id))
            .filter(
                PlacementHistory.tenant_id == tenant_id,
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
                PlacementHistory.tenant_id == tenant_id,
                PlacementHistory.start_date.isnot(None),
                PlacementHistory.start_date >= prev_month_start,
                PlacementHistory.start_date <= prev_month_end,
            )
            .scalar()
            or 0
        )

        match_runs_30d = (
            db.query(func.count(MatchRun.id))
            .filter(
                MatchRun.tenant_id == tenant_id,
                MatchRun.created_at >= now - timedelta(days=30),
            )
            .scalar()
            or 0
        )

        pending_docs = (
            db.query(func.count(Document.id))
            .filter(
                Document.tenant_id == tenant_id,
                Document.verification_status == "PENDING",
            )
            .scalar()
            or 0
        )

        open_incidents = (
            db.query(func.count(Incident.id))
            .filter(Incident.tenant_id == tenant_id, Incident.status == "OPEN")
            .scalar()
            or 0
        )

        check_ins_today = (
            db.query(func.count(AttendanceRecord.id))
            .filter(
                AttendanceRecord.tenant_id == tenant_id,
                AttendanceRecord.checkin_time.isnot(None),
                AttendanceRecord.checkin_time >= day_start,
            )
            .scalar()
            or 0
        )

        visits_next_7 = (
            db.query(func.count(Visit.id))
            .filter(
                Visit.tenant_id == tenant_id,
                Visit.scheduled_start.isnot(None),
                Visit.scheduled_start >= now,
                Visit.scheduled_start <= week_end,
            )
            .scalar()
            or 0
        )

        elder_prospects_open = (
            db.query(func.count(ElderProspect.id))
            .filter(
                ElderProspect.tenant_id == tenant_id,
                ElderProspect.status == "OPEN",
            )
            .scalar()
            or 0
        )
        caregiver_prospects_open = (
            db.query(func.count(CaregiverProspect.id))
            .filter(
                CaregiverProspect.tenant_id == tenant_id,
                CaregiverProspect.status == "OPEN",
            )
            .scalar()
            or 0
        )
        overdue_follow_ups = (
            db.query(func.count(CaregiverProspect.id))
            .filter(
                CaregiverProspect.tenant_id == tenant_id,
                CaregiverProspect.status == "OPEN",
                CaregiverProspect.next_follow_up_at.isnot(None),
                CaregiverProspect.next_follow_up_at < now,
            )
            .scalar()
            or 0
        )

        bench_ready: list[dict] = []
        for cg in sorted(bench, key=lambda c: c.id)[:25]:
            readiness = ReadinessService.compute(db, cg)
            band = readiness["readiness_band"]
            if readiness["readiness_score"] >= 60:
                bench_ready.append(
                    {
                        "caregiver_id": cg.id,
                        "name": f"{cg.first_name} {cg.last_name}".strip(),
                        "readiness_score": readiness["readiness_score"],
                        "readiness_band": band,
                        "top_gaps": readiness["recommendations"][:3],
                    }
                )

        bench_ready.sort(key=lambda x: x["readiness_score"], reverse=True)
        bench_ready = bench_ready[:10]

        # readiness bands for all active (sample when large tenant)
        all_bands: Counter[str] = Counter()
        for cg in active_caregivers[:40]:
            r = ReadinessService.compute(db, cg)
            all_bands[r["readiness_band"]] += 1
        if len(active_caregivers) > 40:
            all_bands_note = f"bands computed for first 40 of {len(active_caregivers)} caregivers"
        else:
            all_bands_note = None

        city_counter: Counter[str] = Counter()
        for cg in bench:
            city = _city_from_attrs(cg.custom_attributes)
            if city:
                city_counter[city] += 1
        bench_by_city = [
            {"city": city, "bench_count": count}
            for city, count in city_counter.most_common(8)
        ]

        police_pending = sum(
            1
            for c in active_caregivers
            if (c.police_verification_status or "").upper() not in ("VERIFIED", "APPROVED")
        )

        return {
            "tenant_id": tenant_id,
            "as_of_utc": now.isoformat() + "Z",
            "workforce": {
                "caregivers_active": len(active_caregivers),
                "caregivers_on_bench": len(bench),
                "caregivers_on_active_assignment": len(assigned_caregiver_ids),
                "utilization_percent": utilization_pct,
                "police_verification_not_verified": police_pending,
            },
            "elders": {
                "active": len(active_elders),
                "without_active_assignment": len(elders_needing_care),
            },
            "assignments": {
                "active": len(active_assignments),
                "started_this_month": assignments_this_month,
                "started_last_month": assignments_last_month,
                "placement_starts_this_month": placements_this_month,
                "placement_starts_last_month": placements_last_month,
            },
            "readiness": {
                "bands_sample": dict(all_bands),
                "bands_sample_note": all_bands_note,
                "bench_ready_for_deployment": bench_ready,
            },
            "pipeline": {
                "elder_prospects_open": elder_prospects_open,
                "caregiver_prospects_open": caregiver_prospects_open,
                "overdue_recruiter_follow_ups": overdue_follow_ups,
            },
            "operations": {
                "pending_document_reviews": pending_docs,
                "open_incidents": open_incidents,
                "attendance_check_ins_today": check_ins_today,
                "visits_scheduled_next_7_days": visits_next_7,
                "matching_runs_last_30_days": match_runs_30d,
            },
            "locations": {
                "bench_by_city": bench_by_city,
            },
            "limitations": [
                "Attrition risk is not modeled yet; use bench and verification gaps as proxies.",
                "Bench city uses caregiver address in profile attributes when present.",
                "Readiness bands may be sampled when caregiver count is large.",
            ],
        }
