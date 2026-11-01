"""Six-monthly reassessment (pricing review 2026-10-03: "6-monthly reassessments on all tiers").

A client's next assessment is due 182 days after their last completed one. It
shows on the dashboard and on Schedule from three weeks before the due date
until an assessment job is booked for it. A client with no completed
assessment yet is "first assessment needed".
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.care_job import CareJob
from app.models.elder import Elder
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord

INTERVAL = timedelta(days=182)
HEADS_UP = timedelta(days=21)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def last_completed(db: Session, elder_id: int) -> datetime | None:
    # Only the two dates: the row itself carries megabytes of saved versions.
    row = (
        db.query(HomeSafetyAssessmentRecord.completed_at, HomeSafetyAssessmentRecord.updated_at)
        .filter(HomeSafetyAssessmentRecord.elder_id == elder_id, HomeSafetyAssessmentRecord.status == "completed")
        .order_by(HomeSafetyAssessmentRecord.completed_at.desc().nullslast())
        .first()
    )
    if not row:
        return None
    return _aware(row.completed_at or row.updated_at)


def due_info(db: Session, elder: Elder, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    last = last_completed(db, elder.id)
    due = (last + INTERVAL) if last else None
    booked = (
        db.query(CareJob)
        .filter(
            CareJob.elder_id == elder.id,
            CareJob.kind == "assessment",
            CareJob.status.notin_(("cancelled", "missed", "completed")),
        )
        .order_by(CareJob.scheduled_at)
        .first()
    )
    return {
        "last_assessed_at": last.isoformat() if last else None,
        "due_at": due.isoformat() if due else None,
        "booked_job_id": booked.id if booked else None,
        "booked_at": _aware(booked.scheduled_at).isoformat() if booked and booked.scheduled_at else None,
        "overdue": bool(due and due < now),
        "needs_first": last is None,
        # A started (not yet completed) assessment: "No assessment on record" would be wrong.
        "has_draft": db.query(HomeSafetyAssessmentRecord.id)
        .filter(HomeSafetyAssessmentRecord.elder_id == elder.id, HomeSafetyAssessmentRecord.status == "draft")
        .first()
        is not None,
    }


def due_list(db: Session, elders: list[Elder], *, now: datetime | None = None) -> list[dict]:
    """Clients whose (re)assessment needs booking now: due within 3 weeks or overdue, not yet booked."""
    now = now or datetime.now(timezone.utc)
    out = []
    for e in elders:
        info = due_info(db, e, now=now)
        if info["booked_job_id"]:
            continue
        due = datetime.fromisoformat(info["due_at"]) if info["due_at"] else None
        if info["needs_first"] or (due and due - now <= HEADS_UP):
            out.append(
                {
                    "elder_id": e.id,
                    "elder_name": f"{e.first_name} {e.last_name}".strip(),
                    "label": "First home safety assessment" if info["needs_first"] else "6-monthly reassessment",
                    **info,
                }
            )
    out.sort(key=lambda r: (not r["overdue"], r["due_at"] or ""))
    return out
