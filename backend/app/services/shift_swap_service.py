"""Shift swap — caregiver cover request with manager approval."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.responses import raise_bad_request, raise_not_found
from app.core.workflow_events import SHIFT_SWAP_REQUESTED
from app.models.caregiver import Caregiver
from app.models.elder import Elder
from app.models.shift_swap_request import ShiftSwapRequest
from app.models.user import User
from app.models.visit import Visit
from app.services.audit_service import AuditService
from app.services.auto_scheduling_service import AutoSchedulingService
from app.services.workflow_emitter import emit_workflow_event


class ShiftSwapService:

    @staticmethod
    def _name(cg: Caregiver | None) -> str:
        if not cg:
            return "Unknown"
        return f"{cg.first_name} {cg.last_name}".strip() or "Unknown"

    @classmethod
    def _to_dict(
        cls,
        db: Session,
        row: ShiftSwapRequest,
        visit: Visit | None = None,
    ) -> dict:
        if visit is None:
            visit = db.query(Visit).filter(Visit.id == row.visit_id).first()
        req_cg = (
            db.query(Caregiver)
            .filter(Caregiver.id == row.requesting_caregiver_id)
            .first()
        )
        rep_cg = None
        if row.replacement_caregiver_id:
            rep_cg = (
                db.query(Caregiver)
                .filter(Caregiver.id == row.replacement_caregiver_id)
                .first()
            )
        elder = None
        if visit:
            elder = db.query(Elder).filter(Elder.id == visit.elder_id).first()
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "visit_id": row.visit_id,
            "requesting_caregiver_id": row.requesting_caregiver_id,
            "requesting_caregiver_name": cls._name(req_cg),
            "replacement_caregiver_id": row.replacement_caregiver_id,
            "replacement_caregiver_name": cls._name(rep_cg) if rep_cg else None,
            "elder_id": visit.elder_id if visit else None,
            "elder_name": cls._name(elder) if elder else None,
            "scheduled_start": visit.scheduled_start if visit else None,
            "scheduled_end": visit.scheduled_end if visit else None,
            "reason": row.reason,
            "status": row.status,
            "resolved_at": row.resolved_at,
            "resolved_by_user_id": row.resolved_by_user_id,
            "resolution_note": row.resolution_note,
            "created_at": row.created_at,
        }

    @staticmethod
    def _as_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @classmethod
    def _validate_visit_for_swap(cls, visit: Visit, caregiver_id: int) -> None:
        now = datetime.now(timezone.utc)
        if visit.caregiver_id != caregiver_id:
            raise_bad_request("You are not assigned to this shift")
        if visit.status != "SCHEDULED":
            raise_bad_request("Only scheduled shifts can be swapped")
        if cls._as_utc(visit.scheduled_start) <= now:
            raise_bad_request("Cannot swap a shift that has already started")
        if visit.attendance_record_id:
            raise_bad_request("Shift already has attendance linked")

    @staticmethod
    def _validate_replacement(
        db: Session,
        visit: Visit,
        replacement_id: int,
        requesting_id: int,
    ) -> Caregiver:
        if replacement_id == requesting_id:
            raise_bad_request("Replacement must be a different caregiver")
        rep = (
            db.query(Caregiver)
            .filter(
                Caregiver.id == replacement_id,
                Caregiver.tenant_id == visit.tenant_id,
                Caregiver.status == "ACTIVE",
            )
            .first()
        )
        if not rep:
            raise_not_found("Replacement caregiver not found")
        if AutoSchedulingService._has_conflict(
            db,
            replacement_id,
            visit.scheduled_start,
            visit.scheduled_end,
        ):
            raise_bad_request("Replacement caregiver has a scheduling conflict")
        return rep

    @classmethod
    def list_coworkers(cls, db: Session, caregiver: Caregiver) -> list[dict]:
        rows = (
            db.query(Caregiver)
            .filter(
                Caregiver.tenant_id == caregiver.tenant_id,
                Caregiver.status == "ACTIVE",
                Caregiver.id != caregiver.id,
            )
            .order_by(Caregiver.first_name, Caregiver.last_name)
            .limit(50)
            .all()
        )
        return [
            {"caregiver_id": c.id, "name": cls._name(c)}
            for c in rows
        ]

    @classmethod
    def create_request(
        cls,
        db: Session,
        caregiver: Caregiver,
        *,
        visit_id: int,
        replacement_caregiver_id: int | None,
        reason: str | None,
        actor: User,
    ) -> dict:
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit or visit.tenant_id != caregiver.tenant_id:
            raise_not_found("Visit not found")
        cls._validate_visit_for_swap(visit, caregiver.id)

        pending = (
            db.query(ShiftSwapRequest)
            .filter(
                ShiftSwapRequest.visit_id == visit_id,
                ShiftSwapRequest.status == "PENDING",
            )
            .first()
        )
        if pending:
            raise_bad_request("A pending swap request already exists for this shift")

        if replacement_caregiver_id is not None:
            cls._validate_replacement(
                db,
                visit,
                replacement_caregiver_id,
                caregiver.id,
            )

        row = ShiftSwapRequest(
            tenant_id=visit.tenant_id,
            visit_id=visit.id,
            requesting_caregiver_id=caregiver.id,
            replacement_caregiver_id=replacement_caregiver_id,
            reason=(reason or "").strip() or None,
            status="PENDING",
        )
        db.add(row)
        db.flush()

        elder = db.query(Elder).filter(Elder.id == visit.elder_id).first()
        emit_workflow_event(
            db,
            tenant_id=visit.tenant_id,
            event_type=SHIFT_SWAP_REQUESTED,
            entity_type="shift_swap_request",
            entity_id=row.id,
            payload={
                "visit_id": visit.id,
                "elder_id": visit.elder_id,
                "elder_name": cls._name(elder),
                "requesting_caregiver_id": caregiver.id,
                "requesting_caregiver_name": cls._name(caregiver),
                "replacement_caregiver_id": replacement_caregiver_id,
                "scheduled_start": visit.scheduled_start.isoformat(),
                "reason": row.reason,
                "summary": (
                    f"{cls._name(caregiver)} requested shift cover "
                    f"for {cls._name(elder)}"
                ),
            },
        )
        AuditService.log(
            db,
            tenant_id=visit.tenant_id,
            user_id=actor.id,
            entity_type="shift_swap_request",
            entity_id=row.id,
            action="CREATED",
            new_value={
                "visit_id": visit.id,
                "replacement_caregiver_id": replacement_caregiver_id,
            },
        )
        db.commit()
        db.refresh(row)
        return cls._to_dict(db, row, visit)

    @classmethod
    def list_requests(
        cls,
        db: Session,
        tenant_id: int | None,
        *,
        status: str | None = None,
        caregiver_id: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        query = db.query(ShiftSwapRequest).order_by(
            ShiftSwapRequest.created_at.desc()
        )
        if tenant_id is not None:
            query = query.filter(ShiftSwapRequest.tenant_id == tenant_id)
        if status:
            query = query.filter(ShiftSwapRequest.status == status.upper())
        if caregiver_id is not None:
            query = query.filter(
                ShiftSwapRequest.requesting_caregiver_id == caregiver_id
            )
        rows = query.limit(limit).all()
        return [cls._to_dict(db, r) for r in rows]

    @classmethod
    def approve(
        cls,
        db: Session,
        request_id: int,
        user: User,
        *,
        replacement_caregiver_id: int | None = None,
    ) -> dict:
        row = (
            db.query(ShiftSwapRequest)
            .filter(ShiftSwapRequest.id == request_id)
            .first()
        )
        if not row:
            raise_not_found("Swap request not found")
        if row.status != "PENDING":
            raise_bad_request("Only pending requests can be approved")

        visit = db.query(Visit).filter(Visit.id == row.visit_id).first()
        if not visit:
            raise_not_found("Visit not found")

        rep_id = replacement_caregiver_id or row.replacement_caregiver_id
        if rep_id is None:
            raise_bad_request("Specify replacement caregiver to approve")

        cls._validate_replacement(
            db,
            visit,
            rep_id,
            row.requesting_caregiver_id,
        )

        old_caregiver_id = visit.caregiver_id
        visit.caregiver_id = rep_id
        row.replacement_caregiver_id = rep_id
        row.status = "APPROVED"
        row.resolved_at = datetime.now(timezone.utc)
        row.resolved_by_user_id = user.id

        AuditService.log(
            db,
            tenant_id=row.tenant_id,
            user_id=user.id,
            entity_type="visit",
            entity_id=visit.id,
            action="SHIFT_SWAP_APPROVED",
            old_value={"caregiver_id": old_caregiver_id},
            new_value={"caregiver_id": rep_id, "swap_request_id": row.id},
        )
        db.commit()
        db.refresh(row)
        return cls._to_dict(db, row, visit)

    @classmethod
    def reject(
        cls,
        db: Session,
        request_id: int,
        user: User,
        *,
        reason: str | None = None,
    ) -> dict:
        row = (
            db.query(ShiftSwapRequest)
            .filter(ShiftSwapRequest.id == request_id)
            .first()
        )
        if not row:
            raise_not_found("Swap request not found")
        if row.status != "PENDING":
            raise_bad_request("Only pending requests can be rejected")

        row.status = "REJECTED"
        row.resolved_at = datetime.now(timezone.utc)
        row.resolved_by_user_id = user.id
        row.resolution_note = (reason or "").strip() or None

        AuditService.log(
            db,
            tenant_id=row.tenant_id,
            user_id=user.id,
            entity_type="shift_swap_request",
            entity_id=row.id,
            action="REJECTED",
            new_value={"reason": row.resolution_note},
        )
        db.commit()
        db.refresh(row)
        return cls._to_dict(db, row)

    @classmethod
    def cancel(
        cls,
        db: Session,
        request_id: int,
        caregiver: Caregiver,
        actor: User,
    ) -> dict:
        row = (
            db.query(ShiftSwapRequest)
            .filter(ShiftSwapRequest.id == request_id)
            .first()
        )
        if not row:
            raise_not_found("Swap request not found")
        if row.requesting_caregiver_id != caregiver.id:
            raise_bad_request("You can only cancel your own requests")
        if row.status != "PENDING":
            raise_bad_request("Only pending requests can be cancelled")

        row.status = "CANCELLED"
        row.resolved_at = datetime.now(timezone.utc)
        row.resolved_by_user_id = actor.id

        AuditService.log(
            db,
            tenant_id=row.tenant_id,
            user_id=actor.id,
            entity_type="shift_swap_request",
            entity_id=row.id,
            action="CANCELLED",
        )
        db.commit()
        db.refresh(row)
        return cls._to_dict(db, row)

    @staticmethod
    def list_upcoming_shifts(db: Session, caregiver: Caregiver, days: int = 14) -> list[dict]:
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days)
        visits = (
            db.query(Visit)
            .filter(
                Visit.caregiver_id == caregiver.id,
                Visit.status == "SCHEDULED",
            )
            .order_by(Visit.scheduled_start)
            .all()
        )
        visits = [
            v
            for v in visits
            if ShiftSwapService._as_utc(v.scheduled_start) >= now
            and ShiftSwapService._as_utc(v.scheduled_start) < end
        ]
        out: list[dict] = []
        for v in visits:
            elder = db.query(Elder).filter(Elder.id == v.elder_id).first()
            pending = (
                db.query(ShiftSwapRequest)
                .filter(
                    ShiftSwapRequest.visit_id == v.id,
                    ShiftSwapRequest.status == "PENDING",
                )
                .first()
            )
            out.append(
                {
                    "visit_id": v.id,
                    "assignment_id": v.assignment_id,
                    "elder_id": v.elder_id,
                    "elder_name": ShiftSwapService._name(elder),
                    "scheduled_start": v.scheduled_start,
                    "scheduled_end": v.scheduled_end,
                    "status": v.status,
                    "pending_swap_id": pending.id if pending else None,
                }
            )
        return out
