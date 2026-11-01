from datetime import date

from sqlalchemy.orm import Session

from app.core.rbac import assert_tenant_access
from app.core.responses import raise_bad_request, raise_not_found
from app.models.assignment import Assignment
from app.models.match_result import MatchResult
from app.models.match_run import MatchRun
from app.models.placement_history import PlacementHistory
from app.models.user import User
from app.schemas.assignment import AssignmentCreate, AssignmentFromMatchRequest

VALID_ASSIGNMENT_STATUSES = frozenset({"ACTIVE", "ENDED"})


class AssignmentService:

    @staticmethod
    def get_assignment(db: Session, assignment_id: int, user: User) -> Assignment:
        row = db.query(Assignment).filter(Assignment.id == assignment_id).first()
        if not row:
            raise_not_found("Assignment not found")
        assert_tenant_access(user, row.tenant_id)
        return row

    @staticmethod
    def _assert_no_active_duplicate(
        db: Session,
        tenant_id: int,
        elder_id: int,
        caregiver_id: int,
        exclude_id: int | None = None,
    ) -> None:
        query = db.query(Assignment).filter(
            Assignment.tenant_id == tenant_id,
            Assignment.elder_id == elder_id,
            Assignment.caregiver_id == caregiver_id,
            Assignment.status == "ACTIVE",
        )
        if exclude_id is not None:
            query = query.filter(Assignment.id != exclude_id)
        if query.first():
            raise_bad_request(
                "An active assignment already exists for this elder and caregiver"
            )

    @staticmethod
    def _record_placement_start(
        db: Session,
        assignment: Assignment,
        outcome: str = "ACTIVE",
    ) -> None:
        db.add(
            PlacementHistory(
                tenant_id=assignment.tenant_id,
                elder_id=assignment.elder_id,
                caregiver_id=assignment.caregiver_id,
                assignment_id=assignment.id,
                start_date=assignment.start_date,
                outcome=outcome,
            )
        )

    @staticmethod
    def _close_placement_history(
        db: Session,
        assignment: Assignment,
        end_date: date,
        outcome: str = "ENDED",
    ) -> None:
        row = (
            db.query(PlacementHistory)
            .filter(PlacementHistory.assignment_id == assignment.id)
            .order_by(PlacementHistory.id.desc())
            .first()
        )
        if row:
            row.end_date = end_date
            row.outcome = outcome
        else:
            db.add(
                PlacementHistory(
                    tenant_id=assignment.tenant_id,
                    elder_id=assignment.elder_id,
                    caregiver_id=assignment.caregiver_id,
                    assignment_id=assignment.id,
                    start_date=assignment.start_date,
                    end_date=end_date,
                    outcome=outcome,
                )
            )

    @staticmethod
    def list_assignments(db: Session, user: User) -> list[Assignment]:
        query = db.query(Assignment)
        if user.role != "SYSTEM_ADMIN" and user.tenant_id is not None:
            query = query.filter(Assignment.tenant_id == user.tenant_id)
        return query.order_by(Assignment.id.desc()).all()

    @staticmethod
    def create_from_match(
        db: Session,
        data: AssignmentFromMatchRequest,
        user: User,
    ) -> Assignment:
        result = (
            db.query(MatchResult)
            .filter(MatchResult.id == data.match_result_id)
            .first()
        )
        if not result:
            raise_not_found("Match result not found")

        match_run = (
            db.query(MatchRun)
            .filter(MatchRun.id == result.match_run_id)
            .first()
        )
        if not match_run:
            raise_not_found("Match run not found")

        assert_tenant_access(user, match_run.tenant_id)

        AssignmentService._assert_no_active_duplicate(
            db,
            match_run.tenant_id,
            match_run.elder_id,
            result.caregiver_id,
        )

        assignment = Assignment(
            tenant_id=match_run.tenant_id,
            elder_id=match_run.elder_id,
            caregiver_id=result.caregiver_id,
            match_score=result.match_score,
            start_date=data.start_date or date.today(),
            status="ACTIVE",
        )
        db.add(assignment)
        db.flush()

        AssignmentService._record_placement_start(db, assignment)

        result.status = "ACCEPTED"
        db.commit()
        db.refresh(assignment)
        return assignment

    @staticmethod
    def create_manual(
        db: Session,
        data: AssignmentCreate,
        user: User,
    ) -> Assignment:
        from app.services.elder_service import ElderService
        from app.services.caregiver_service import CaregiverService

        elder = ElderService.get_elder(db, data.elder_id, user)
        caregiver = CaregiverService.get_caregiver(db, data.caregiver_id, user)

        if elder.tenant_id != caregiver.tenant_id:
            raise_bad_request("Elder and caregiver must belong to the same tenant")

        status = (data.status or "ACTIVE").upper()
        if status not in VALID_ASSIGNMENT_STATUSES:
            raise_bad_request("status must be ACTIVE or ENDED")
        if status == "ACTIVE":
            AssignmentService._assert_no_active_duplicate(
                db,
                elder.tenant_id,
                data.elder_id,
                data.caregiver_id,
            )

        assignment = Assignment(
            tenant_id=elder.tenant_id,
            elder_id=data.elder_id,
            caregiver_id=data.caregiver_id,
            match_score=data.match_score,
            start_date=data.start_date or date.today(),
            end_date=data.end_date,
            status=status,
        )
        db.add(assignment)
        db.flush()
        if status == "ACTIVE":
            AssignmentService._record_placement_start(db, assignment)
        db.commit()
        db.refresh(assignment)
        return assignment

    @staticmethod
    def end_assignment(
        db: Session,
        assignment_id: int,
        user: User,
        end_date: date | None = None,
    ) -> Assignment:
        assignment = AssignmentService.get_assignment(db, assignment_id, user)
        if assignment.status == "ENDED":
            raise_bad_request("Assignment is already ended")
        if assignment.status != "ACTIVE":
            raise_bad_request(f"Cannot end assignment with status {assignment.status}")

        ended = end_date or date.today()
        assignment.status = "ENDED"
        assignment.end_date = ended
        AssignmentService._close_placement_history(db, assignment, ended)
        db.commit()
        db.refresh(assignment)
        return assignment
