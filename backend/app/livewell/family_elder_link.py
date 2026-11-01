"""Ensure a prospect has an elder record so family portal publish can run.

On convert, assessments / photos / AI jobs move to the elder and the prospect
row is deleted — the client is the sole identity afterward.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.pipeline_constants import (
    ACTIVITY_STAGE_CHANGE,
    PROSPECT_STATUS_LOST,
    PROSPECT_STATUS_OPEN,
    PROSPECT_STATUS_WON,
)
from app.core.responses import raise_bad_request, raise_not_found
from app.models.document import Document
from app.models.elder import Elder
from app.models.elder_prospect import ElderProspect
from app.models.home_safety_ai_job import HomeSafetyAIJob
from app.models.home_safety_assessment import HomeSafetyAssessmentRecord
from app.models.pipeline_activity import PipelineActivity
from app.models.user import User
from app.schemas.elder import ElderCreate
from app.services.audit_service import AuditService
from app.services.elder_service import ElderService


def _prospect_audit_snapshot(row: ElderProspect) -> dict:
    return {
        "prospect_id": int(row.id),
        "first_name": row.first_name,
        "last_name": row.last_name,
        "phone": row.phone,
        "stage": row.stage,
        "status": row.status,
        "converted_elder_id": row.converted_elder_id,
    }


def absorb_prospect_into_elder(
    db: Session,
    *,
    prospect_id: int,
    elder_id: int,
    keep_lead: bool = False,
) -> None:
    """Reassign prospect-linked data to the elder, then delete the prospect.

    ``keep_lead`` (sales board "Won"): move the data but keep the lead row and its
    stage history, so the Won column still shows how the deal was closed.

    Assessments, AI jobs, and documents are kept and pointed at the client.
    Pipeline activities (prospect-only) are removed with the lead row.
    """
    row = db.query(ElderProspect).filter(ElderProspect.id == prospect_id).first()
    if not row:
        return

    elder = db.query(Elder).filter(Elder.id == elder_id).first()
    if not elder:
        raise_not_found("Client not found")

    if elder.tenant_id != row.tenant_id:
        raise_bad_request("Prospect and client must belong to the same tenant")

    if not elder.care_level and row.care_level:
        elder.care_level = row.care_level
    if not elder.phone and row.phone:
        elder.phone = row.phone
    if not elder.address and row.address:
        elder.address = row.address

    assessments = (
        db.query(HomeSafetyAssessmentRecord)
        .filter(HomeSafetyAssessmentRecord.prospect_id == prospect_id)
        .all()
    )
    for assessment in assessments:
        assessment.elder_id = elder_id
        assessment.prospect_id = None
        payload = dict(assessment.payload or {})
        payload["elderId"] = elder_id
        payload["prospectId"] = None
        assessment.payload = payload

    db.query(HomeSafetyAIJob).filter(HomeSafetyAIJob.prospect_id == prospect_id).update(
        {
            HomeSafetyAIJob.elder_id: elder_id,
            HomeSafetyAIJob.prospect_id: None,
        },
        synchronize_session=False,
    )

    db.query(Document).filter(
        Document.entity_type == "elder_prospect",
        Document.entity_id == prospect_id,
    ).update(
        {
            Document.entity_type: "elder",
            Document.entity_id: elder_id,
        },
        synchronize_session=False,
    )

    if keep_lead:
        db.flush()
        return

    db.query(PipelineActivity).filter(
        PipelineActivity.elder_prospect_id == prospect_id
    ).delete(synchronize_session=False)

    db.delete(row)
    db.flush()


def ensure_elder_for_prospect(
    db: Session,
    user: User,
    prospect_id: int,
    *,
    auto_from_assessment: bool = False,
    link_to_elder_id: int | None = None,
) -> int:
    """Return elder id for prospect, converting if needed, then absorb the lead.

    When ``link_to_elder_id`` is set, attach that existing elder instead of creating a new one
    (used when the assessor picked a client on intake).
    """
    row = db.query(ElderProspect).filter(ElderProspect.id == prospect_id).first()
    if not row:
        raise_not_found("Prospect not found")
    if row.status == PROSPECT_STATUS_LOST:
        raise_bad_request("Cannot convert a lost prospect")

    if row.converted_elder_id:
        elder_id = int(row.converted_elder_id)
        absorb_prospect_into_elder(db, prospect_id=prospect_id, elder_id=elder_id)
        return elder_id

    if link_to_elder_id is not None:
        elder = (
            db.query(Elder)
            .filter(Elder.id == link_to_elder_id, Elder.tenant_id == row.tenant_id)
            .first()
        )
        if not elder:
            raise_not_found("Client not found")
        elder_id = int(elder.id)
        before = _prospect_audit_snapshot(row)
        row.stage = "WON"
        row.status = PROSPECT_STATUS_WON
        row.converted_elder_id = elder_id
        AuditService.log(
            db,
            tenant_id=row.tenant_id,
            user_id=user.id,
            entity_type="elder_prospect",
            entity_id=int(row.id),
            action="prospect_linked_to_elder",
            old_value=before,
            new_value={
                **_prospect_audit_snapshot(row),
                "elder_id": elder_id,
                "auto_from_assessment": auto_from_assessment,
                "linked_existing": True,
            },
        )
        body = (
            f"Linked assessment prospect to existing elder #{elder_id}"
            if auto_from_assessment
            else f"Linked to existing elder #{elder_id}"
        )
        db.add(
            PipelineActivity(
                tenant_id=row.tenant_id,
                elder_prospect_id=row.id,
                activity_type=ACTIVITY_STAGE_CHANGE,
                body=body,
                metadata_={
                    "elder_id": elder_id,
                    "auto_from_assessment": auto_from_assessment,
                    "linked_existing": True,
                },
                created_by_user_id=user.id,
            )
        )
        db.flush()
        absorb_prospect_into_elder(db, prospect_id=prospect_id, elder_id=elder_id)
        return elder_id

    elder = ElderService.create_elder(
        db,
        ElderCreate(
            tenant_id=row.tenant_id,
            first_name=row.first_name,
            last_name=row.last_name,
            phone=row.phone,
            address=row.address,
            care_level=row.care_level,
            status="ACTIVE",
        ),
        user,
    )
    elder_id = int(elder.id)
    before = _prospect_audit_snapshot(row)
    row.stage = "WON"
    row.status = PROSPECT_STATUS_WON
    row.converted_elder_id = elder_id
    AuditService.log(
        db,
        tenant_id=row.tenant_id,
        user_id=user.id,
        entity_type="elder_prospect",
        entity_id=int(row.id),
        action="prospect_converted_to_elder",
        old_value=before,
        new_value={
            **_prospect_audit_snapshot(row),
            "elder_id": elder_id,
            "auto_from_assessment": auto_from_assessment,
            "linked_existing": False,
        },
    )
    body = (
        f"Auto-converted to elder #{elder_id} after LiveWell360 assessment complete"
        if auto_from_assessment
        else f"Converted to elder #{elder_id}"
    )
    db.add(
        PipelineActivity(
            tenant_id=row.tenant_id,
            elder_prospect_id=row.id,
            activity_type=ACTIVITY_STAGE_CHANGE,
            body=body,
            metadata_={"elder_id": elder_id, "auto_from_assessment": auto_from_assessment},
            created_by_user_id=user.id,
        )
    )
    db.flush()
    absorb_prospect_into_elder(db, prospect_id=prospect_id, elder_id=elder_id)
    return elder_id


def unlink_elder_from_prospect(
    db: Session,
    user: User,
    prospect_id: int,
) -> ElderProspect:
    """Clear prospect↔client link and reopen the prospect in the pipeline.

    Only applies to legacy WON rows that were not yet absorbed. New converts
    delete the prospect, so unlink is unavailable for them.
    """
    row = db.query(ElderProspect).filter(ElderProspect.id == prospect_id).first()
    if not row:
        raise_not_found("Prospect not found")
    if not row.converted_elder_id:
        raise_bad_request("Prospect is not linked to a client")

    previous_elder_id = int(row.converted_elder_id)
    before = _prospect_audit_snapshot(row)
    row.converted_elder_id = None
    row.status = PROSPECT_STATUS_OPEN
    if row.stage == "WON":
        row.stage = "ASSESSMENT_DONE"
    AuditService.log(
        db,
        tenant_id=row.tenant_id,
        user_id=user.id,
        entity_type="elder_prospect",
        entity_id=int(row.id),
        action="prospect_unlinked_from_elder",
        old_value=before,
        new_value={**_prospect_audit_snapshot(row), "previous_elder_id": previous_elder_id},
    )
    db.add(
        PipelineActivity(
            tenant_id=row.tenant_id,
            elder_prospect_id=row.id,
            activity_type=ACTIVITY_STAGE_CHANGE,
            body=f"Unlinked from client #{previous_elder_id}; prospect reopened",
            metadata_={"previous_elder_id": previous_elder_id, "unlinked": True},
            created_by_user_id=user.id,
        )
    )
    db.flush()
    return row


def republish_latest_assessment_for_elder(
    db: Session,
    *,
    tenant_id: int,
    elder_id: int,
    prospect_id: int | None = None,
) -> bool:
    """Publish the newest completed assessment linked to this elder/prospect."""
    from app.livewell.family_publish import publish_assessment_to_family
    from sqlalchemy import or_

    q = db.query(HomeSafetyAssessmentRecord).filter(
        HomeSafetyAssessmentRecord.tenant_id == tenant_id,
        HomeSafetyAssessmentRecord.status == "completed",
    )
    if prospect_id is not None:
        q = q.filter(
            or_(
                HomeSafetyAssessmentRecord.elder_id == elder_id,
                HomeSafetyAssessmentRecord.prospect_id == prospect_id,
            )
        )
    else:
        q = q.filter(HomeSafetyAssessmentRecord.elder_id == elder_id)

    rows = q.all()
    if not rows:
        return False
    rows.sort(
        key=lambda r: (r.completed_at or r.updated_at or r.created_at).isoformat()
        if (r.completed_at or r.updated_at or r.created_at)
        else "",
        reverse=True,
    )
    row = rows[0]

    payload = dict(row.payload or {})
    payload["id"] = row.assessment_id
    payload["elderId"] = elder_id
    payload["prospectId"] = None
    if row.completed_at and not payload.get("completedAt"):
        payload["completedAt"] = row.completed_at.isoformat()

    row.elder_id = elder_id
    row.prospect_id = None
    row.payload = payload

    return publish_assessment_to_family(
        db,
        elder_id=elder_id,
        tenant_id=tenant_id,
        payload=payload,
    )


def absorb_legacy_converted_prospects_for_elder(db: Session, elder_id: int) -> int:
    """Absorb any leftover WON prospects still pointing at this elder. Returns count."""
    rows = (
        db.query(ElderProspect)
        .filter(ElderProspect.converted_elder_id == elder_id)
        .all()
    )
    for row in rows:
        absorb_prospect_into_elder(db, prospect_id=int(row.id), elder_id=elder_id)
    return len(rows)
