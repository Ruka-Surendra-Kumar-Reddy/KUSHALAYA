"""Caregiver leave requests with manager approval."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.core.responses import raise_bad_request, raise_not_found
from app.core.workflow_events import LEAVE_REQUESTED
from app.models.caregiver import Caregiver
from app.models.leave_request import LeaveRequest
from app.models.user import User
from app.schemas.leave import LEAVE_TYPES
from app.services.audit_service import AuditService
from app.services.workflow_emitter import emit_workflow_event


class LeaveService:

    @staticmethod
    def _name(cg: Caregiver | None) -> str:
        if not cg:
            return "Unknown"
        return f"{cg.first_name} {cg.last_name}".strip() or "Unknown"

    @classmethod
    def _to_dict(cls, db: Session, row: LeaveRequest) -> dict:
        cg = (
            db.query(Caregiver)
            .filter(Caregiver.id == row.caregiver_id)
            .first()
        )
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "caregiver_id": row.caregiver_id,
            "caregiver_name": cls._name(cg),
            "leave_type": row.leave_type,
            "start_date": row.start_date,
            "end_date": row.end_date,
            "reason": row.reason,
            "status": row.status,
            "resolved_at": row.resolved_at,
            "resolved_by_user_id": row.resolved_by_user_id,
            "resolution_note": row.resolution_note,
            "created_at": row.created_at,
        }

    @staticmethod
    def _validate_dates(start_date: date, end_date: date) -> None:
        if end_date < start_date:
            raise_bad_request("End date must be on or after start date")
        if start_date < date.today():
            raise_bad_request("Leave cannot start in the past")

    @classmethod
    def _check_overlap(
        cls,
        db: Session,
        caregiver_id: int,
        start_date: date,
        end_date: date,
        exclude_id: int | None = None,
    ) -> None:
        query = db.query(LeaveRequest).filter(
            LeaveRequest.caregiver_id == caregiver_id,
            LeaveRequest.status.in_(("PENDING", "APPROVED")),
            LeaveRequest.start_date <= end_date,
            LeaveRequest.end_date >= start_date,
        )
        if exclude_id is not None:
            query = query.filter(LeaveRequest.id != exclude_id)
        if query.first():
            raise_bad_request("Overlapping leave request already exists")

    @classmethod
    def create(
        cls,
        db: Session,
        caregiver: Caregiver,
        *,
        leave_type: str,
        start_date: date,
        end_date: date,
        reason: str | None,
        actor: User,
    ) -> dict:
        leave_type = leave_type.upper()
        if leave_type not in LEAVE_TYPES:
            raise_bad_request(f"Invalid leave type. Use one of: {', '.join(sorted(LEAVE_TYPES))}")

        cls._validate_dates(start_date, end_date)
        cls._check_overlap(db, caregiver.id, start_date, end_date)

        row = LeaveRequest(
            tenant_id=caregiver.tenant_id,
            caregiver_id=caregiver.id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            status="PENDING",
        )
        db.add(row)
        db.flush()

        emit_workflow_event(
            db,
            tenant_id=caregiver.tenant_id,
            event_type=LEAVE_REQUESTED,
            entity_type="leave_request",
            entity_id=row.id,
            payload={
                "leave_request_id": row.id,
                "caregiver_id": caregiver.id,
                "caregiver_name": cls._name(caregiver),
                "leave_type": leave_type,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "reason": reason,
                "summary": (
                    f"{cls._name(caregiver)} requested {leave_type.lower()} leave "
                    f"{start_date} to {end_date}"
                ),
            },
            commit=False,
        )

        AuditService.log(
            db,
            tenant_id=caregiver.tenant_id,
            user_id=actor.id,
            entity_type="leave_request",
            entity_id=row.id,
            action="CREATED",
            new_value={
                "leave_type": leave_type,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        )

        db.commit()
        db.refresh(row)
        return cls._to_dict(db, row)

    @classmethod
    def list_requests(
        cls,
        db: Session,
        tenant_id: int | None,
        *,
        caregiver_id: int | None = None,
        status: str | None = None,
    ) -> list[dict]:
        query = db.query(LeaveRequest).order_by(LeaveRequest.created_at.desc())
        if tenant_id is not None:
            query = query.filter(LeaveRequest.tenant_id == tenant_id)
        if caregiver_id is not None:
            query = query.filter(LeaveRequest.caregiver_id == caregiver_id)
        if status:
            query = query.filter(LeaveRequest.status == status.upper())
        return [cls._to_dict(db, row) for row in query.limit(100).all()]

    @classmethod
    def _get_row(cls, db: Session, request_id: int) -> LeaveRequest:
        row = db.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
        if not row:
            raise_not_found("Leave request not found")
        return row

    @classmethod
    def cancel(cls, db: Session, request_id: int, caregiver: Caregiver, actor: User) -> dict:
        row = cls._get_row(db, request_id)
        if row.caregiver_id != caregiver.id:
            raise_bad_request("Not your leave request")
        if row.status != "PENDING":
            raise_bad_request("Only pending requests can be cancelled")
        row.status = "CANCELLED"
        row.resolved_at = datetime.now(timezone.utc)
        row.resolved_by_user_id = actor.id
        db.commit()
        db.refresh(row)
        return cls._to_dict(db, row)

    @classmethod
    def approve(cls, db: Session, request_id: int, actor: User) -> dict:
        from app.core.rbac import assert_tenant_access

        row = cls._get_row(db, request_id)
        assert_tenant_access(actor, row.tenant_id)
        if row.status != "PENDING":
            raise_bad_request("Only pending requests can be approved")
        cls._check_overlap(db, row.caregiver_id, row.start_date, row.end_date, exclude_id=row.id)

        row.status = "APPROVED"
        row.resolved_at = datetime.now(timezone.utc)
        row.resolved_by_user_id = actor.id

        AuditService.log(
            db,
            tenant_id=row.tenant_id,
            user_id=actor.id,
            entity_type="leave_request",
            entity_id=row.id,
            action="APPROVED",
            new_value={"caregiver_id": row.caregiver_id},
        )

        db.commit()
        db.refresh(row)
        return cls._to_dict(db, row)

    @classmethod
    def reject(
        cls,
        db: Session,
        request_id: int,
        actor: User,
        reason: str | None = None,
    ) -> dict:
        from app.core.rbac import assert_tenant_access

        row = cls._get_row(db, request_id)
        assert_tenant_access(actor, row.tenant_id)
        if row.status != "PENDING":
            raise_bad_request("Only pending requests can be rejected")

        row.status = "REJECTED"
        row.resolved_at = datetime.now(timezone.utc)
        row.resolved_by_user_id = actor.id
        row.resolution_note = reason

        AuditService.log(
            db,
            tenant_id=row.tenant_id,
            user_id=actor.id,
            entity_type="leave_request",
            entity_id=row.id,
            action="REJECTED",
            new_value={"reason": reason},
        )

        db.commit()
        db.refresh(row)
        return cls._to_dict(db, row)
