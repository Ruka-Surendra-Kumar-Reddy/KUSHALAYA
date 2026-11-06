"""Start (or continue) a home safety assessment from the office — for a client or a lead.

The checklist screen (caregiver app, also used by Ops) works on an assessment
care job, and a care job needs a client record. For a lead that is not Won yet
we create a hidden client record: status INACTIVE (so it stays out of client
lists, dashboards and digests) with ``custom_attributes["lead_id"]``. We do NOT
set ``converted_elder_id`` on the lead: that marks it as a client in the funnel
and GET /elders absorbs (deletes) such leads. When the lead is moved to Won,
``sales_pipeline._won_elder`` picks this record up, so the assessment stays
linked to the client.

An office-started assessment is dated now with its assessment id set: no
"scheduled" notice to the family and the missed-visit timer leaves it alone.

An unfinished assessment (open assessment job, or a draft assessment record) is
offered as "Continue the draft" instead of silently starting a second one.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.pipeline_constants import PROSPECT_STATUS_OPEN
from app.core.rbac import resolve_tenant_id
from app.core.responses import raise_bad_request
from app.livewell.care_jobs import OPEN_STATUSES, _elder_for, serialize
from app.models.care_job import CareJob
from app.models.elder import Elder
from app.models.elder_prospect import ElderProspect
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord
from app.models.user import User

LEAD_KEY = "lead_id"
LEAD_RECORD_STATUS = "INACTIVE"
TITLE = "Home safety assessment"


def lead_id_of(elder: Elder | None) -> int | None:
    """The lead this hidden client record was made for (None for real clients)."""
    if elder is None or elder.status != LEAD_RECORD_STATUS:
        return None
    raw = (elder.custom_attributes or {}).get(LEAD_KEY) if isinstance(elder.custom_attributes, dict) else None
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def is_lead_record(elder: Elder) -> bool:
    return lead_id_of(elder) is not None


def lead_record(db: Session, lead: ElderProspect) -> Elder | None:
    """The client record already used for this lead's assessment, if any."""
    if lead.converted_elder_id:
        return db.get(Elder, int(lead.converted_elder_id))
    rows = (
        db.query(Elder)
        .filter(Elder.tenant_id == lead.tenant_id, Elder.status == LEAD_RECORD_STATUS)
        .order_by(Elder.id.desc())
        .all()
    )
    return next((e for e in rows if lead_id_of(e) == lead.id), None)


def _lead_record_or_create(db: Session, user: User, lead: ElderProspect) -> Elder:
    from app.schemas.elder import ElderCreate
    from app.services.elder_service import ElderService

    found = lead_record(db, lead)
    if found is not None:
        return found
    return ElderService.create_elder(
        db,
        ElderCreate(
            tenant_id=lead.tenant_id,
            first_name=lead.first_name or "Lead",
            last_name=lead.last_name or "",
            phone=lead.phone,
            address=lead.address,
            care_level=lead.care_level,
            status=LEAD_RECORD_STATUS,
            # Email has no column: kept with the extra details step 1 shows (field_assessment.EXTRA_FIELDS).
            custom_attributes={LEAD_KEY: lead.id, "email": lead.email or ""},
        ),
        user,
    )


def _answered(payload: dict | None) -> int:
    return len((payload or {}).get("ratings") or {})


def find_draft(db: Session, elder_id: int | None, lead_id: int | None = None) -> dict | None:
    """The newest unfinished assessment: an open assessment job, else a draft record."""
    if elder_id:
        job = (
            db.query(CareJob)
            .filter(CareJob.elder_id == elder_id, CareJob.kind == "assessment", CareJob.status.in_(OPEN_STATUSES))
            .order_by(CareJob.id.desc())
            .first()
        )
        if job is not None:
            rec = None
            if job.assessment_id:
                rec = (
                    db.query(HomeSafetyAssessmentRecord)
                    .filter(HomeSafetyAssessmentRecord.assessment_id == job.assessment_id)
                    .first()
                )
            return {
                "job_id": job.id,
                "assessment_id": job.assessment_id,
                "answered": _answered(rec.payload if rec else None),
                "since": (job.checked_in_at or job.scheduled_at or job.created_at).isoformat()
                if (job.checked_in_at or job.scheduled_at or job.created_at)
                else None,
            }
    clauses = []
    if elder_id:
        clauses.append(HomeSafetyAssessmentRecord.elder_id == elder_id)
    if lead_id:
        clauses.append(HomeSafetyAssessmentRecord.prospect_id == lead_id)
    if not clauses:
        return None
    rec = (
        db.query(HomeSafetyAssessmentRecord)
        .filter(or_(*clauses), HomeSafetyAssessmentRecord.status == "draft")
        .order_by(HomeSafetyAssessmentRecord.updated_at.desc(), HomeSafetyAssessmentRecord.id.desc())
        .first()
    )
    if rec is None:
        return None
    return {
        "job_id": None,
        "assessment_id": rec.assessment_id,
        "answered": _answered(rec.payload),
        "since": rec.updated_at.isoformat() if rec.updated_at else None,
    }


def _lead(db: Session, user: User, lead_id: int) -> ElderProspect:
    from app.livewell.sales_pipeline import _lead_for

    return _lead_for(db, user, lead_id)


def _target(db: Session, user: User, elder_id: int | None, lead_id: int | None) -> tuple[Elder | None, ElderProspect | None]:
    if bool(elder_id) == bool(lead_id):
        raise_bad_request("Choose a client or a lead")
    if elder_id:
        return _elder_for(db, user, int(elder_id)), None
    lead = _lead(db, user, int(lead_id))
    from app.livewell.sales_pipeline import board_stage

    stage = board_stage(lead)
    if stage == "LOST":
        raise_bad_request("This lead is closed as Lost. Move it back to an open stage first.")
    elder = lead_record(db, lead)
    if elder is not None:
        _elder_for(db, user, elder.id)  # tenant / team check
    return elder, lead


def draft_for(db: Session, user: User, *, elder_id: int | None = None, lead_id: int | None = None) -> dict | None:
    elder, lead = _target(db, user, elder_id, lead_id)
    return find_draft(db, elder.id if elder else None, lead.id if lead else None)


def advance_lead(db: Session, user: User | None, lead: ElderProspect, to: str, note: str) -> bool:
    """Move a lead forward to "Assessment booked" / "Assessment done" (never back,
    never out of Won / Lost / follow-ups). No commit: the caller commits."""
    from app.core.pipeline_constants import ACTIVITY_STAGE_CHANGE
    from app.livewell.sales_pipeline import STAGE_LABELS, board_stage
    from app.models.pipeline_activity import PipelineActivity

    order = ("NEW", "ASSESSMENT_SCHEDULED", "ASSESSMENT_DONE")
    current = board_stage(lead)
    if current not in order or to not in order or order.index(to) <= order.index(current):
        return False
    lead.stage = to
    lead.status = PROSPECT_STATUS_OPEN
    db.add(
        PipelineActivity(
            tenant_id=lead.tenant_id,
            elder_prospect_id=lead.id,
            activity_type=ACTIVITY_STAGE_CHANGE,
            body=f"{STAGE_LABELS[current]} → {STAGE_LABELS[to]}: {note}",
            metadata_={"from": current, "to": to, "comment": note, "auto": True},
            created_by_user_id=user.id if user else None,
        )
    )
    return True


def lead_assessment_done(db: Session, user: User | None, elder: Elder) -> None:
    """A lead's checklist was submitted: its card moves to "Assessment done"."""
    lid = lead_id_of(elder)
    if lid is None:
        return
    lead = db.get(ElderProspect, lid)
    if lead is not None and lead.tenant_id == elder.tenant_id:
        advance_lead(db, user, lead, "ASSESSMENT_DONE", "Assessment submitted")


def _discard_office_drafts(db: Session, elder_id: int) -> None:
    """"Start a new one": the client's unfinished office drafts are closed, so they do
    not pile up or come back as "continue". Caregiver visits are left alone."""
    from app.livewell.assessment_service import DISCARDED

    open_jobs = (
        db.query(CareJob)
        .filter(CareJob.elder_id == elder_id, CareJob.kind == "assessment", CareJob.status.in_(OPEN_STATUSES))
        .all()
    )
    keep = {j.assessment_id for j in open_jobs if j.caregiver_id and j.assessment_id}
    for j in open_jobs:
        if not j.caregiver_id:
            j.status = "cancelled"
    drafts = db.query(HomeSafetyAssessmentRecord).filter(
        HomeSafetyAssessmentRecord.elder_id == elder_id, HomeSafetyAssessmentRecord.status == "draft"
    )
    for rec in drafts.all():
        if rec.assessment_id not in keep:
            rec.status = DISCARDED


def start(
    db: Session,
    user: User,
    *,
    elder_id: int | None = None,
    lead_id: int | None = None,
    new: bool = False,
) -> dict:
    """Open the checklist: continue the unfinished draft (default) or start a new one."""
    elder, lead = _target(db, user, elder_id, lead_id)
    if not new:
        draft = find_draft(db, elder.id if elder else None, lead.id if lead else None)
        if draft and draft["job_id"]:
            return {"job_id": draft["job_id"], "resumed": True, "elder_id": elder.id if elder else None}
    else:
        draft = None
        if elder is not None:
            _discard_office_drafts(db, elder.id)
    if elder is None:
        elder = _lead_record_or_create(db, user, lead)
    now = datetime.now(timezone.utc)
    job = CareJob(
        tenant_id=elder.tenant_id,
        elder_id=elder.id,
        kind="assessment",
        title=TITLE,
        tasks="",
        location=(elder.address or "").strip()[:500],
        # Dated now and created directly (not through create_job): no "scheduled"
        # notice to the family. Not "checked in" either, so the family app shows no
        # "caregiver arrived" card for an office assessment.
        scheduled_at=now,
        status="scheduled",
        product_ids="",
        staff_note="Started from the office",
        # The care manager doing it: whoever starts it from the office.
        assignee_user_id=user.id if user.role in ("CARE_MANAGER", "TENANT_ADMIN", "SYSTEM_ADMIN") else None,
        created_by_user_id=user.id,
    )
    db.add(job)
    db.flush()
    # A draft record without an open job is picked up where it was left. Having an
    # assessment id also keeps the missed-visit timer away (daily_checks).
    job.assessment_id = draft["assessment_id"] if draft else f"field-job-{job.id}"
    if lead is not None:
        advance_lead(db, user, lead, "ASSESSMENT_SCHEDULED", "Assessment started")
    db.commit()
    db.refresh(job)
    return {"job_id": job.id, "resumed": bool(draft), "elder_id": elder.id, "job": serialize(db, job)}


def book(
    db: Session,
    user: User,
    *,
    lead_id: int,
    scheduled_at: datetime,
    assignee_user_id: int | None = None,
    force: bool = False,
) -> dict:
    """"Book assessment" on a lead (e.g. "visit us in 3 days" on a call): an assessment
    job at that time for the lead's client record, and the lead moves to "Assessment booked"."""
    from app.livewell.care_jobs import IST, _aware, create_job

    lead = _lead(db, user, int(lead_id))
    elder = _lead_record_or_create(db, user, lead)
    job = create_job(
        db,
        user,
        {
            "elder_id": elder.id,
            "kind": "assessment",
            "scheduled_at": scheduled_at,
            "assignee_user_id": assignee_user_id,
            "force": force,
            "staff_note": "Booked from the lead",
        },
    )
    db.refresh(lead)
    when = _aware(scheduled_at).astimezone(IST).strftime("%a %d %b, %I:%M %p IST")
    advance_lead(db, user, lead, "ASSESSMENT_SCHEDULED", f"Assessment booked for {when}")
    db.commit()
    from app.livewell.team_alerts import alert_team

    alert_team(db, lead.tenant_id, "assessment_booked", f"Assessment booked: {lead.first_name} {lead.last_name}",
               f"Booked by {user.first_name} {user.last_name}.", path="/kushalaya/enquiries")
    return {"job": job, "lead_id": lead.id, "stage": lead.stage}


def targets(db: Session, user: User) -> list[dict]:
    """Who "New assessment" can start for: clients, then open leads (labelled)."""
    from app.services.elder_service import ElderService

    out: list[dict] = []
    for e in ElderService.list_elders(db, user):
        if e.status == LEAD_RECORD_STATUS:
            continue
        out.append(
            {
                "key": f"client:{e.id}",
                "kind": "client",
                "elder_id": e.id,
                "lead_id": None,
                "name": f"{e.first_name} {e.last_name}".strip(),
                "phone": e.phone or "",
                "ref": f"C{e.id}",  # client ID shown and searchable in "New assessment"
                "draft": find_draft(db, e.id),
            }
        )
    try:
        from app.services.prospect_service import ProspectService

        ProspectService._assert_elder_prospects(db, user)
    except Exception:  # noqa: BLE001 - no leads module for this agency: clients only
        return out
    q = db.query(ElderProspect).filter(ElderProspect.status == PROSPECT_STATUS_OPEN)
    tid = resolve_tenant_id(user)
    if tid is not None:
        q = q.filter(ElderProspect.tenant_id == tid)
    for lead in q.order_by(ElderProspect.updated_at.desc()).limit(500).all():
        if lead.stage in ("WON", "LOST") or lead.converted_elder_id:
            continue
        rec = lead_record(db, lead)
        out.append(
            {
                "key": f"lead:{lead.id}",
                "kind": "lead",
                "elder_id": None,
                "lead_id": lead.id,
                "name": f"{lead.first_name} {lead.last_name}".strip() or "No name",
                "phone": lead.phone or "",
                "ref": f"L{lead.id}",
                "draft": find_draft(db, rec.id if rec else None, lead.id),
            }
        )
    return out


def board(db: Session, user: User) -> list[dict]:
    """The Assessments page: every assessment as one row, bucketed scheduled /
    in_progress / completed. Open jobs without answers are "scheduled"; with answers,
    "in_progress"; finished jobs and completed records are "completed"."""
    from app.livewell.assessment_service import DISCARDED
    from app.livewell.care_jobs import team_elder_ids
    from app.models.caregiver import Caregiver

    tid = resolve_tenant_id(user)
    jq = db.query(CareJob).filter(CareJob.kind == "assessment", CareJob.status != "cancelled")
    rq = db.query(HomeSafetyAssessmentRecord).filter(HomeSafetyAssessmentRecord.status != DISCARDED)
    if tid is not None:
        jq = jq.filter(CareJob.tenant_id == tid)
        rq = rq.filter(HomeSafetyAssessmentRecord.tenant_id == tid)
    team = team_elder_ids(db, user)
    if team is not None:
        jq = jq.filter(CareJob.elder_id.in_(team or {-1}))
        rq = rq.filter(HomeSafetyAssessmentRecord.elder_id.in_(team or {-1}))
    jobs = jq.order_by(CareJob.id.desc()).limit(500).all()
    records = {r.assessment_id: r for r in rq.order_by(HomeSafetyAssessmentRecord.id.desc()).limit(1000).all()}
    elders = {e.id: e for e in db.query(Elder).filter(Elder.id.in_({j.elder_id for j in jobs} | {
        r.elder_id for r in records.values() if r.elder_id} or {-1}))}
    cgs = {c.id: c for c in db.query(Caregiver).filter(Caregiver.id.in_({j.caregiver_id for j in jobs if j.caregiver_id} or {-1}))}
    staff = {u.id: u for u in db.query(User).filter(User.id.in_({j.assignee_user_id for j in jobs if j.assignee_user_id} or {-1}))}
    now = datetime.now(timezone.utc)

    def iso(d):
        # Naive DB datetimes are UTC; say so, or the browser reads them as local (IST) time.
        if not d:
            return None
        return (d if d.tzinfo or not isinstance(d, datetime) else d.replace(tzinfo=timezone.utc)).isoformat()

    def client(e: Elder | None) -> dict:
        if e is None:
            return {"client_name": "", "client_phone": "", "area": "", "is_lead": False}
        attrs = e.custom_attributes if isinstance(e.custom_attributes, dict) else {}
        name = " ".join(x for x in (e.first_name if e.first_name != "Lead" else "", e.last_name) if x)
        return {
            "client_name": name or "No name",
            "client_phone": e.phone or "",
            "area": ", ".join(x for x in (attrs.get("area"), attrs.get("city")) if x) or (e.address or "")[:60],
            "is_lead": lead_id_of(e) is not None,
        }

    out: list[dict] = []
    seen: set[str] = set()
    for j in jobs:
        rec = records.get(j.assessment_id) if j.assessment_id else None
        if j.assessment_id:
            seen.add(j.assessment_id)
        payload = (rec.payload if rec else None) or {}
        answered = len(payload.get("ratings") or {})
        if j.status == "completed" or (rec is not None and rec.status == "completed"):
            bucket = "completed"
        elif j.status == "missed":
            bucket = "scheduled"
        else:
            bucket = "in_progress" if answered else "scheduled"
        when = j.scheduled_at
        if when is not None and when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        overdue = (now - when).days if bucket == "scheduled" and when and when < now else 0
        cg = cgs.get(j.caregiver_id) if j.caregiver_id else None
        out.append({
            "key": f"job-{j.id}",
            "job_id": j.id,
            "assessment_id": j.assessment_id,
            "status": bucket,
            "job_status": j.status,
            **client(elders.get(j.elder_id)),
            "elder_id": j.elder_id,
            "caregiver_id": j.caregiver_id,
            "caregiver_name": f"{cg.first_name} {cg.last_name}".strip() if cg else "",
            "care_manager_id": j.assignee_user_id,
            "care_manager_name": (
                f"{staff[j.assignee_user_id].first_name} {staff[j.assignee_user_id].last_name}".strip()
                if j.assignee_user_id in staff else ""
            ),
            "scheduled_at": iso(j.scheduled_at),
            "updated_at": iso(rec.updated_at if rec else j.created_at),
            "completed_at": iso(j.completed_at) or payload.get("completedAt"),
            "answered": answered,
            "score": payload.get("independenceScore"),
            "overdue_days": overdue,
            "office": not j.caregiver_id and (j.staff_note or "") == "Started from the office",
        })
    for aid, rec in records.items():
        if aid in seen or rec.status != "completed":
            continue  # old-form drafts without a job cannot be continued
        payload = rec.payload or {}
        e = elders.get(rec.elder_id) if rec.elder_id else None
        row = {**client(e)}
        if e is None:
            row["client_name"] = " ".join(x for x in (payload.get("clientFirstName"), payload.get("clientLastName")) if x) or "Client"
        out.append({
            "key": f"rec-{aid}",
            "job_id": None,
            "assessment_id": aid,
            "status": "completed",
            "job_status": "completed",
            **row,
            "elder_id": rec.elder_id,
            "caregiver_id": None,
            "caregiver_name": str(payload.get("assessorName") or ""),
            "care_manager_id": None,
            "care_manager_name": str(payload.get("assessorName") or ""),
            "scheduled_at": None,
            "updated_at": iso(rec.updated_at),
            "completed_at": payload.get("completedAt") or iso(rec.updated_at),
            "answered": len(payload.get("ratings") or {}),
            "score": payload.get("independenceScore"),
            "overdue_days": 0,
            "office": False,
        })
    return out
