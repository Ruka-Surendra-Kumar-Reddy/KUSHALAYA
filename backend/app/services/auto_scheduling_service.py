"""WorkforceOS auto-scheduling — scored shift generation with conflict and hour limits."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.rbac import resolve_tenant_id
from app.core.responses import raise_bad_request
from app.models.assignment import Assignment
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.visit import Visit
from app.models.user import User
from app.schemas.scheduling import AutoScheduleRequest
from app.services.matching.scoring import score_availability, score_location
from app.services.scheduling_service import SchedulingService, WEEKDAY_MAP

ACTIVE_VISIT_STATUSES = frozenset({"SCHEDULED", "IN_PROGRESS"})


class AutoSchedulingService:

    @staticmethod
    def _week_start(day: date) -> date:
        return day - timedelta(days=day.weekday())

    @staticmethod
    def _visit_hours(visit: Visit) -> float:
        delta = visit.scheduled_end - visit.scheduled_start
        return max(0.0, delta.total_seconds() / 3600.0)

    @staticmethod
    def _caregiver_weekly_hours(
        db: Session,
        caregiver_id: int,
        week_start: date,
        pending: list[dict],
    ) -> float:
        week_end = week_start + timedelta(days=7)
        start_dt = datetime.combine(week_start, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(week_end, datetime.min.time(), tzinfo=timezone.utc)

        visits = (
            db.query(Visit)
            .filter(
                Visit.caregiver_id == caregiver_id,
                Visit.scheduled_start >= start_dt,
                Visit.scheduled_start < end_dt,
                Visit.status.in_(ACTIVE_VISIT_STATUSES | {"COMPLETED"}),
            )
            .all()
        )
        total = sum(AutoSchedulingService._visit_hours(v) for v in visits)
        for slot in pending:
            if slot["caregiver_id"] != caregiver_id:
                continue
            if week_start <= slot["day"] < week_end:
                total += slot["duration_hours"]
        return total

    @staticmethod
    def _has_conflict(
        db: Session,
        caregiver_id: int,
        start: datetime,
        end: datetime,
    ) -> bool:
        visits = (
            db.query(Visit)
            .filter(
                Visit.caregiver_id == caregiver_id,
                Visit.status.in_(ACTIVE_VISIT_STATUSES),
                Visit.scheduled_start < end,
                Visit.scheduled_end > start,
            )
            .all()
        )
        return len(visits) > 0

    @staticmethod
    def _preferred_start_hour(elder: Elder, caregiver: Caregiver, default: int) -> int:
        elder_sched = (elder.custom_attributes or {}).get("schedule_requirements") or {}
        caregiver_avail = (caregiver.custom_attributes or {}).get("availability") or {}
        for source in (elder_sched, caregiver_avail):
            if isinstance(source, dict) and source.get("preferred_start_hour") is not None:
                try:
                    hour = int(source["preferred_start_hour"])
                    if 0 <= hour <= 23:
                        return hour
                except (TypeError, ValueError):
                    pass
        return default

    @staticmethod
    def _score_slot(elder: Elder, caregiver: Caregiver) -> tuple[float, list[str]]:
        avail_score, avail_reasons = score_availability(elder, caregiver)
        loc_score, loc_reasons = score_location(elder, caregiver)
        score = round((avail_score * 0.6 + loc_score * 0.4) * 100, 1)
        reasons = avail_reasons + loc_reasons
        return score, reasons

    @staticmethod
    def _uncovered_clients(db: Session, tid: int | None) -> list[dict]:
        elder_q = db.query(Elder).filter(Elder.status == "ACTIVE")
        assign_q = db.query(Assignment).filter(Assignment.status == "ACTIVE")
        if tid is not None:
            elder_q = elder_q.filter(Elder.tenant_id == tid)
            assign_q = assign_q.filter(Assignment.tenant_id == tid)

        covered = {a.elder_id for a in assign_q.all()}
        out: list[dict] = []
        for elder in elder_q.all():
            if elder.id in covered:
                continue
            days = SchedulingService._elder_schedule_days(elder)
            if not days:
                continue
            out.append(
                {
                    "elder_id": elder.id,
                    "elder_name": SchedulingService._display_name(
                        elder.first_name,
                        elder.last_name,
                    ),
                    "schedule_days": sorted(
                        k for k, v in WEEKDAY_MAP.items() if v in days
                    ),
                }
            )
        return out

    @staticmethod
    def auto_schedule(
        db: Session,
        data: AutoScheduleRequest,
        user: User,
    ) -> dict:
        if data.end_date < data.start_date:
            raise_bad_request("end_date must be on or after start_date")

        tid = resolve_tenant_id(user)
        assign_q = db.query(Assignment).filter(Assignment.status == "ACTIVE")
        if tid is not None:
            assign_q = assign_q.filter(Assignment.tenant_id == tid)
        assignments = assign_q.all()

        proposals: list[dict] = []
        pending_slots: list[dict] = []
        created = 0
        skipped = 0
        conflicts = 0

        day = data.start_date
        while day <= data.end_date:
            weekday = day.weekday()
            for assignment in assignments:
                elder = (
                    db.query(Elder).filter(Elder.id == assignment.elder_id).first()
                )
                caregiver = (
                    db.query(Caregiver)
                    .filter(Caregiver.id == assignment.caregiver_id)
                    .first()
                )
                if not elder or not caregiver:
                    continue
                if weekday not in SchedulingService._elder_schedule_days(elder):
                    continue

                start_hour = AutoSchedulingService._preferred_start_hour(
                    elder,
                    caregiver,
                    data.default_start_hour,
                )
                start_dt = datetime.combine(
                    day,
                    datetime.min.time().replace(hour=start_hour),
                    tzinfo=timezone.utc,
                )
                end_dt = start_dt + timedelta(hours=data.default_duration_hours)

                exists = (
                    db.query(Visit)
                    .filter(
                        Visit.assignment_id == assignment.id,
                        Visit.scheduled_start == start_dt,
                    )
                    .first()
                )
                if exists:
                    skipped += 1
                    proposals.append(
                        {
                            "assignment_id": assignment.id,
                            "elder_id": assignment.elder_id,
                            "caregiver_id": assignment.caregiver_id,
                            "day": day.isoformat(),
                            "scheduled_start": start_dt.isoformat(),
                            "scheduled_end": end_dt.isoformat(),
                            "action": "skip",
                            "score": None,
                            "reasons": ["Visit already scheduled"],
                        }
                    )
                    continue

                if AutoSchedulingService._has_conflict(
                    db,
                    assignment.caregiver_id,
                    start_dt,
                    end_dt,
                ):
                    conflicts += 1
                    proposals.append(
                        {
                            "assignment_id": assignment.id,
                            "elder_id": assignment.elder_id,
                            "caregiver_id": assignment.caregiver_id,
                            "day": day.isoformat(),
                            "scheduled_start": start_dt.isoformat(),
                            "scheduled_end": end_dt.isoformat(),
                            "action": "conflict",
                            "score": None,
                            "reasons": ["Caregiver has overlapping shift"],
                        }
                    )
                    continue

                week_start = AutoSchedulingService._week_start(day)
                weekly_hours = AutoSchedulingService._caregiver_weekly_hours(
                    db,
                    assignment.caregiver_id,
                    week_start,
                    pending_slots,
                )
                if weekly_hours + data.default_duration_hours > data.max_hours_per_week:
                    skipped += 1
                    proposals.append(
                        {
                            "assignment_id": assignment.id,
                            "elder_id": assignment.elder_id,
                            "caregiver_id": assignment.caregiver_id,
                            "day": day.isoformat(),
                            "scheduled_start": start_dt.isoformat(),
                            "scheduled_end": end_dt.isoformat(),
                            "action": "skip",
                            "score": None,
                            "reasons": [
                                f"Exceeds {data.max_hours_per_week}h weekly limit "
                                f"({weekly_hours:.1f}h scheduled)"
                            ],
                        }
                    )
                    continue

                score, reasons = AutoSchedulingService._score_slot(elder, caregiver)
                action = "create" if not data.dry_run else "proposed"
                proposal = {
                    "assignment_id": assignment.id,
                    "elder_id": assignment.elder_id,
                    "caregiver_id": assignment.caregiver_id,
                    "elder_name": SchedulingService._display_name(
                        elder.first_name,
                        elder.last_name,
                    ),
                    "caregiver_name": SchedulingService._display_name(
                        caregiver.first_name,
                        caregiver.last_name,
                    ),
                    "day": day.isoformat(),
                    "scheduled_start": start_dt.isoformat(),
                    "scheduled_end": end_dt.isoformat(),
                    "action": action,
                    "score": score,
                    "reasons": reasons,
                }
                proposals.append(proposal)

                if not data.dry_run:
                    db.add(
                        Visit(
                            tenant_id=assignment.tenant_id,
                            assignment_id=assignment.id,
                            elder_id=assignment.elder_id,
                            caregiver_id=assignment.caregiver_id,
                            scheduled_start=start_dt,
                            scheduled_end=end_dt,
                            status="SCHEDULED",
                        )
                    )
                    created += 1

                pending_slots.append(
                    {
                        "caregiver_id": assignment.caregiver_id,
                        "day": day,
                        "duration_hours": data.default_duration_hours,
                    }
                )

            day += timedelta(days=1)

        if not data.dry_run:
            db.commit()

        proposed_count = sum(1 for p in proposals if p["action"] in ("create", "proposed"))

        return {
            "mode": "preview" if data.dry_run else "applied",
            "created": created if not data.dry_run else 0,
            "proposed": proposed_count,
            "skipped": skipped,
            "conflicts": conflicts,
            "assignments": len(assignments),
            "uncovered_clients": AutoSchedulingService._uncovered_clients(db, tid),
            "proposals": proposals[:200],
        }
