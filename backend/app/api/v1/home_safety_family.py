from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import require_elder_portal, READ_ROLES, WRITE_ROLES, require_roles
from app.livewell.family_service import HomeSafetyFamilyService
from app.livewell.photo_service import HomeSafetyPhotoService
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.services.session_activity_service import SessionActivityService
from app.schemas.home_safety_family import (
    EmergencyContactResponse,
    FamilyActiveElderRequest,
    FamilyAlertResponse,
    FamilyApprovedVisualResponse,
    FamilyCareFeedItemResponse,
    FamilyCircleInviteRequest,
    FamilyCircleMemberResponse,
    FamilyCircleRemoveResponse,
    FamilyStaffInboxRowResponse,
    FamilyStaffReadResponse,
    FamilyStaffThreadResponse,
    FamilyStaffUnlinkResponse,
    FamilyDashboardResponse,
    FamilyDigestPrefsResponse,
    FamilyDigestPrefsUpdate,
    FamilyDigestPreviewResponse,
    FamilyDocumentResponse,
    FamilyDocumentTypeResponse,
    FamilyEldersListResponse,
    FamilyImprovementPlanResponse,
    FamilyIncidentResolve,
    FamilyIncidentResponse,
    FamilyMessageCreate,
    FamilyMessageResponse,
    FamilyPhotoResponse,
    FamilyPlanItemResponse,
    FamilyPlanItemStatusUpdate,
    FamilyScheduleResponse,
    FamilyServiceRequestCreate,
    FamilyServiceRequestResponse,
    FamilyServiceRequestStaffUpdate,
    FamilyServiceTypeResponse,
    FamilyShareBriefResponse,
    FamilySosCreate,
    FamilyStaffLinkRequest,
    FamilyStaffLinkResponse,
    FamilyVisitResponse,
    SafetyScoreResponse,
    WellnessReportResponse,
)
from app.schemas.home_safety_visit import VisitExperienceRatingRequest
from app.schemas.family_receipts import FamilyDeviceResponse, FamilyReceiptResponse
from app.schemas.family_wallet import (
    WalletBalanceResponse,
    WalletRechargeCreate,
    WalletRechargeResponse,
    WalletRechargeSettleRequest,
    WalletRechargeVerifyRequest,
    WalletTransactionResponse,
)
from app.livewell.visit_service import HomeSafetyVisitService
from app.livewell.family_care_hub import FamilyCareHubService
from app.livewell.family_service_requests import FamilyServiceRequestService
from app.livewell.family_devices import FamilyDeviceService
from app.livewell.family_receipts import FamilyReceiptService
from app.livewell.wallet_recharge_service import WalletRechargeService
from app.livewell.wallet_service import WalletService
from app.core.config import settings
from app.core.money import format_minor
from app.services.elder_portal_service import ElderPortalService

router = APIRouter(
    prefix="/home-safety/family",
    tags=["Safe Home — Family App"],
)

care_router = APIRouter(
    prefix="/home-safety/care",
    tags=["Safe Home — Family Care (staff)"],
)


@router.get("/public/care-team-contact")
def public_care_team_contact(db: Session = Depends(get_db)):
    """Care-team phone + WhatsApp for the signed-out login page ("Trouble signing in?").

    Deliberately public (the founder's number is the default); same agency the
    public website uses.
    """
    from app.livewell.care_team_contact import get_contact
    from app.models.tenant import Tenant

    return get_contact(db.query(Tenant).order_by(Tenant.id).first())


@router.get("/dashboard", response_model=FamilyDashboardResponse)
def family_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return HomeSafetyFamilyService.dashboard(db, current_user)


@router.get("/elders", response_model=FamilyEldersListResponse)
def family_list_elders(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return HomeSafetyFamilyService.list_elders(db, current_user)


@router.post("/elders/active", response_model=FamilyEldersListResponse)
def family_set_active_elder(
    body: FamilyActiveElderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return HomeSafetyFamilyService.set_active_elder(db, current_user, body.elder_id)


@router.get("/safety-score", response_model=SafetyScoreResponse)
def family_safety_score(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return HomeSafetyFamilyService.safety_score(db, current_user)


@router.get("/improvement-plan", response_model=FamilyImprovementPlanResponse)
def family_improvement_plan(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return HomeSafetyFamilyService.improvement_plan(db, current_user)


@router.get("/share-brief", response_model=FamilyShareBriefResponse)
def family_share_brief(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return HomeSafetyFamilyService.share_brief(db, current_user)


@router.get("/wellness-reports", response_model=list[WellnessReportResponse])
def family_wellness_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return HomeSafetyFamilyService.wellness_reports(db, current_user)


@router.get("/visits", response_model=list[FamilyVisitResponse])
def family_visits(
    days: int = 60,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return HomeSafetyFamilyService.visit_history(db, current_user, days=days)


@router.get("/visits/{visit_id}", response_model=FamilyVisitResponse)
def family_visit_detail(
    visit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    from app.livewell.visit_reports import family_photo_items

    from app.models.care_job import CareJob
    from app.livewell.visit_feedback import job_id_from_visit_id

    if visit_id.startswith("job-"):
        out = _family_job_visit(db, current_user, visit_id)  # 404 unless it is this elder's job
        job = db.get(CareJob, job_id_from_visit_id(visit_id) or -1)
        ids = ((job.report if job else None) or {}).get("photo_ids") or []
        if job is not None:
            from app.livewell.care_jobs import family_caregiver_name, family_visit_times

            # Real check-in / finish / duration only (a same-minute finish is hidden).
            out.update(family_visit_times(job))
            # The caregiver's first name (+ last initial), else the name on the report.
            name = family_caregiver_name(db, job, full=True)
            if name:
                out["staff_name"] = name
    else:
        out = dict(HomeSafetyFamilyService.visit_detail(db, current_user, visit_id))
        ids = out.get("photo_ids") or []
    # Only photos of this family's elder, with caption + time for the report grid.
    photos = family_photo_items(db, ElderPortalService.get_linked_elder(db, current_user), ids)
    out["photos"] = photos
    out["photo_ids"] = [p["id"] for p in photos]
    out["photo_urls"] = [p["url"] for p in photos]
    return out


def _family_job_visit(db: Session, user: User, visit_id: str) -> dict:
    """A care-job visit for the family (#106 rating, #100 shared voice notes only)."""
    from app.core.responses import raise_not_found
    from app.livewell.care_jobs import family_jobs
    from app.livewell.visit_feedback import family_voice_notes, job_id_from_visit_id

    upcoming, recent = family_jobs(db, user)
    for v in [*recent, *upcoming]:
        if v["id"] == visit_id:
            elder = ElderPortalService.get_linked_elder(db, user)
            return {**v, "voice_notes": family_voice_notes(db, elder, job_id_from_visit_id(visit_id) or -1)}
    raise_not_found("Visit not found")


@router.post("/visits/{visit_id}/experience-rating", response_model=FamilyVisitResponse)
def family_rate_visit_experience(
    visit_id: str,
    body: VisitExperienceRatingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    from app.livewell.visit_feedback import job_id_from_visit_id, rate_visit

    job_id = job_id_from_visit_id(visit_id)
    if job_id is not None:
        rate_visit(db, current_user, ElderPortalService.get_linked_elder(db, current_user), job_id,
                   body.rating, body.comment)
        return _family_job_visit(db, current_user, visit_id)
    return HomeSafetyVisitService.rate_experience_for_family(
        db,
        current_user,
        visit_id,
        rating=body.rating,
        comment=body.comment,
    )


@router.get("/photos", response_model=list[FamilyPhotoResponse])
def family_photos(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return HomeSafetyFamilyService.photos(db, current_user)


@router.get("/visualizations", response_model=list[FamilyApprovedVisualResponse])
def family_visualizations(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    result = HomeSafetyFamilyService.visualizations(db, current_user)
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Viewed approved visualizations",
        summary=f"Opened {len(result)} approved visualization(s)",
        entity_type="family",
        commit=True,
    )
    return result


@router.get("/alerts", response_model=list[FamilyAlertResponse])
def family_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return HomeSafetyFamilyService.alerts(db, current_user)


@router.post("/alerts/{alert_id}/read", response_model=FamilyAlertResponse)
def family_mark_alert_read(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return FamilyCareHubService.mark_alert_read(db, current_user, alert_id)


@router.get("/schedule", response_model=FamilyScheduleResponse)
def family_schedule(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    from app.livewell.care_jobs import family_jobs

    upcoming_jobs, recent_jobs = family_jobs(db, current_user)
    upcoming = [*HomeSafetyVisitService.list_upcoming_for_family(db, current_user), *upcoming_jobs]
    recent = [*HomeSafetyVisitService.list_for_family(db, current_user, days=45), *recent_jobs]
    key = lambda v: str(v.get("visited_at") or "")  # noqa: E731
    return {
        "upcoming": sorted(upcoming, key=key),
        "recent": sorted(recent, key=key, reverse=True)[:12],
    }


@router.get("/live-visit")
def family_live_visit(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """Caregiver on the way to this family's parent (position + rough ETA), or
    "arrived" with the time and no position. Polled every 30 s by Home."""
    from app.livewell.live_location import family_live

    return family_live(db, current_user)


@router.get("/care-feed", response_model=list[FamilyCareFeedItemResponse])
def family_care_feed(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return FamilyCareHubService.care_feed(db, current_user)


@router.get("/messages", response_model=list[FamilyMessageResponse])
def family_messages(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return FamilyCareHubService.list_messages(db, current_user)


@router.post("/messages", response_model=FamilyMessageResponse)
def family_send_message(
    body: FamilyMessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    result = FamilyCareHubService.send_message(db, current_user, body.body)
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Sent family message",
        summary="Family portal message sent to care team",
        entity_type="family",
        commit=True,
    )
    return result


@router.get("/incidents", response_model=list[FamilyIncidentResponse])
def family_incidents(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return FamilyCareHubService.list_incidents(db, current_user)


@router.post("/sos", response_model=FamilyIncidentResponse)
def family_sos(
    body: FamilySosCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    result = FamilyCareHubService.raise_sos(db, current_user, body.note)
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Raised SOS / incident",
        summary=body.note or "Family SOS raised",
        entity_type="incident",
        commit=True,
    )
    return result


@router.post("/incidents/{incident_id}/resolve", response_model=FamilyIncidentResponse)
def family_resolve_incident(
    incident_id: str,
    request: Request,
    body: FamilyIncidentResolve | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    status = (body.status if body else None) or "resolved"
    result = FamilyCareHubService.resolve_incident(db, current_user, incident_id, status=status)
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Resolved care incident",
        summary=f"{result.get('kind')} → {result.get('status')}",
        entity_type="incident",
        entity_id=incident_id,
        commit=True,
    )
    return result


@router.get("/digest-prefs", response_model=FamilyDigestPrefsResponse)
def family_digest_prefs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return FamilyCareHubService.get_prefs(db, current_user)


@router.patch("/digest-prefs", response_model=FamilyDigestPrefsResponse)
def family_update_digest_prefs(
    body: FamilyDigestPrefsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return FamilyCareHubService.update_prefs(db, current_user, body.model_dump(exclude_unset=True))


@router.get("/digest-preview", response_model=FamilyDigestPreviewResponse)
def family_digest_preview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return FamilyCareHubService.digest_preview(db, current_user)


@router.get("/circle", response_model=list[FamilyCircleMemberResponse])
def family_circle(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return FamilyCareHubService.list_circle(db, current_user)


@router.post("/circle/invite", response_model=FamilyCircleMemberResponse)
def family_circle_invite(
    body: FamilyCircleInviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return FamilyCareHubService.invite_member(
        db,
        current_user,
        email=body.email,
        password=body.password,
        phone=body.phone,
        first_name=body.first_name,
        last_name=body.last_name,
        portal_relationship=body.portal_relationship,
        elder_id=body.elder_id,
    )


@router.delete("/circle/{member_id}", response_model=FamilyCircleRemoveResponse)
def family_circle_remove(
    member_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """Primary member only. Removes the person's access to the active elder."""
    result = FamilyCareHubService.remove_member(db, current_user, member_id)
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Removed a family member",
        summary=f"Removed {result.get('email')} from the family circle",
        entity_type="family",
        entity_id=str(member_id),
        commit=True,
    )
    return result


@router.get("/receipts", response_model=list[FamilyReceiptResponse])
def family_receipts(
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """Receipts for every successful wallet movement on the active elder's wallet."""
    return FamilyReceiptService.list_for_family(db, current_user, limit=limit)


@router.get("/receipts/{receipt_id}", response_model=FamilyReceiptResponse)
def family_receipt_detail(
    receipt_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return FamilyReceiptService.get_for_family(db, current_user, receipt_id)


@router.get("/devices", response_model=list[FamilyDeviceResponse])
def family_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """Wearables bound to the active elder, with battery and online state."""
    return FamilyDeviceService.list_for_family(db, current_user)


@router.get("/documents", response_model=list[FamilyDocumentResponse])
def family_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return FamilyCareHubService.list_documents(db, current_user)


@router.get("/document-types", response_model=list[FamilyDocumentTypeResponse])
def family_document_types(
    _current_user: User = Depends(require_elder_portal),
):
    from app.livewell.document_types import FAMILY_UPLOAD_TYPES

    return [{"id": code, "label": label} for code, label in FAMILY_UPLOAD_TYPES]


@router.post("/documents", response_model=FamilyDocumentResponse)
async def family_upload_document(
    request: Request,
    file: UploadFile = File(...),
    document_type: str = Form(...),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """Family shares a document with the care team (medical, insurance, ID…)."""
    content = await file.read()
    result = FamilyCareHubService.upload_document(
        db,
        current_user,
        file_name=file.filename or "document",
        content=content,
        content_type=file.content_type or "application/octet-stream",
        document_type=document_type,
        note=note,
    )
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Uploaded a document",
        summary=f"Family document: {result.get('title')}",
        entity_type="document",
        entity_id=str(result.get("id")),
        meta={"document_type": document_type},
        commit=True,
    )
    return result


@router.get("/documents/{document_id}/file")
def family_document_file(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    content, mime, file_name = FamilyCareHubService.read_document_file(
        db, current_user, document_id
    )
    # PDFs and images are safe to render in place; anything else downloads, so a
    # file the family uploaded can never execute in our origin.
    inline_ok = mime == "application/pdf" or mime.startswith("image/")
    disposition = "inline" if inline_ok else "attachment"
    return Response(
        content=content,
        media_type=mime,
        headers={
            "Content-Disposition": f'{disposition}; filename="{file_name}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/hazards")
def family_hazards(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """Hazards spotted on visits and whether they have been fixed."""
    from app.livewell.visit_reports import list_hazards
    from app.services.elder_portal_service import ElderPortalService

    elder = ElderPortalService.get_linked_elder(db, current_user)
    return [
        {k: h.get(k) for k in ("id", "note", "product_name", "status", "spotted_at", "fixed_at")}
        for h in list_hazards(elder)
        if h.get("status") != "dismissed"
    ]


@router.get("/suggestions")
def family_suggestions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """Products recommended from the latest home safety assessment (price incl. GST, no cost)."""
    from app.livewell.suggestions import family_view, suggestions_for_elder
    from app.services.elder_portal_service import ElderPortalService

    elder = ElderPortalService.get_linked_elder(db, current_user)
    return family_view(suggestions_for_elder(db, elder.tenant_id, elder.id))


@router.get("/service-catalog", response_model=list[FamilyServiceTypeResponse])
def family_service_catalog(
    _current_user: User = Depends(require_elder_portal),
):
    return FamilyServiceRequestService.catalog()


@router.get("/service-requests", response_model=list[FamilyServiceRequestResponse])
def family_list_service_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return FamilyServiceRequestService.list_for_family(db, current_user)


@router.post("/service-requests", response_model=FamilyServiceRequestResponse)
def family_create_service_request(
    body: FamilyServiceRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    result = FamilyServiceRequestService.create_for_family(
        db,
        current_user,
        service_type=body.service_type,
        preferred_at=body.preferred_at.isoformat() if body.preferred_at else None,
        notes=body.notes,
        product_name=body.product_name,
        product_id=body.product_id,
    )
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Requested a service",
        summary=f"Family service request: {body.service_type}",
        entity_type="service_request",
        meta={"service_type": body.service_type},
        commit=True,
    )
    return result


@router.post(
    "/service-requests/{request_id}/cancel",
    response_model=FamilyServiceRequestResponse,
)
def family_cancel_service_request(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return FamilyServiceRequestService.cancel_for_family(db, current_user, request_id)


@router.post(
    "/service-requests/{request_id}/pay",
    response_model=FamilyServiceRequestResponse,
)
def family_pay_service_request(
    request_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """Approve the staff-quoted price — debits the wallet upfront."""
    result = FamilyServiceRequestService.pay_from_wallet(db, current_user, request_id)
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Approved and paid for a service",
        summary=f"Wallet payment for {result.get('service_label')}",
        entity_type="service_request",
        entity_id=request_id,
        meta={"amount_minor": result.get("quoted_amount_minor")},
        commit=True,
    )
    return result


def _wallet_balance_payload(db: Session, current_user: User) -> dict:
    elder = ElderPortalService.get_linked_elder(db, current_user)
    wallet = WalletService.get_or_create(db, elder)
    return {
        "elder_id": elder.id,
        "balance_minor": wallet.balance_minor,
        "balance_display": format_minor(wallet.balance_minor, wallet.currency),
        "currency": wallet.currency,
        "status": wallet.status,
        "min_recharge_minor": int(settings.WALLET_MIN_RECHARGE_MINOR),
        "max_recharge_minor": int(settings.WALLET_MAX_RECHARGE_MINOR),
    }


@router.get("/wallet", response_model=WalletBalanceResponse)
def family_wallet_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return _wallet_balance_payload(db, current_user)


@router.get("/wallet/transactions", response_model=list[WalletTransactionResponse])
def family_wallet_transactions(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    elder = ElderPortalService.get_linked_elder(db, current_user)
    wallet = WalletService.get_or_create(db, elder)
    return [
        {
            "id": entry.public_id,
            "kind": entry.kind,
            "amount_minor": entry.amount_minor,
            "amount_display": format_minor(entry.amount_minor, entry.currency),
            "balance_after_minor": entry.balance_after_minor,
            "currency": entry.currency,
            "status": entry.status,
            "reference_type": entry.reference_type,
            "reference_id": entry.reference_id,
            "note": entry.note,
            "created_at": entry.created_at,
        }
        for entry in WalletService.history(db, wallet, limit=limit)
    ]


@router.post("/wallet/recharge", response_model=WalletRechargeResponse)
def family_wallet_recharge(
    body: WalletRechargeCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    result = WalletRechargeService.start(
        db, current_user, amount_minor=body.amount_minor, quote_order_id=body.quote_order_id
    )
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Started a wallet top-up",
        summary=f"Recharge {format_minor(body.amount_minor)}",
        entity_type="wallet_transaction",
        entity_id=result.get("transaction_id"),
        meta={"amount_minor": body.amount_minor, "provider": result.get("provider")},
        commit=True,
    )
    return result


@router.post("/wallet/recharge/verify", response_model=WalletBalanceResponse)
def family_wallet_recharge_verify(
    body: WalletRechargeVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """Verify the Razorpay checkout callback and credit the wallet.

    Returns 400 without crediting if the signature does not match.
    """
    entry = WalletRechargeService.verify_checkout(
        db,
        current_user,
        order_id=body.razorpay_order_id,
        payment_id=body.razorpay_payment_id,
        signature=body.razorpay_signature,
    )
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Completed a wallet top-up",
        summary=f"Top-up {format_minor(entry.amount_minor)} confirmed",
        entity_type="wallet_transaction",
        entity_id=entry.public_id,
        meta={"payment_id": body.razorpay_payment_id},
        commit=True,
    )
    return _wallet_balance_payload(db, current_user)


@router.post("/wallet/recharge/settle", response_model=WalletBalanceResponse)
def family_wallet_recharge_settle(
    body: WalletRechargeSettleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """Dev/demo only — settles a stub recharge. Rejected on a real gateway."""
    WalletRechargeService.settle_stub(db, current_user, transaction_id=body.transaction_id)
    return _wallet_balance_payload(db, current_user)


@router.post("/wallet/webhook")
async def family_wallet_webhook(request: Request, db: Session = Depends(get_db)):
    """Payment gateway callback.

    Deliberately unauthenticated — the gateway cannot hold a session. Trust
    comes from the HMAC signature over the raw body, which is why the raw bytes
    are read here rather than a parsed model.
    """
    payload = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    return WalletRechargeService.handle_webhook(db, payload=payload, signature=signature)


@router.get("/emergency-contacts", response_model=list[EmergencyContactResponse])
def family_emergency_contacts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    return HomeSafetyFamilyService.emergency_contacts(db, current_user)


@router.get("/photos/{document_id}/image")
def family_photo_image(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    content, mime, file_name = HomeSafetyPhotoService.read_for_family_user(
        db, current_user, document_id
    )
    return Response(
        content=content,
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="{file_name}"'},
    )


@care_router.post(
    "/elders/{elder_id}/family-links",
    response_model=FamilyStaffLinkResponse,
)
def staff_link_family_user(
    elder_id: int,
    body: FamilyStaffLinkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Link an existing family portal login to this elder (multi-senior household)."""
    return HomeSafetyFamilyService.staff_link_family_user(
        db,
        current_user,
        elder_id=elder_id,
        email=body.email,
        set_active=body.set_active,
    )


@care_router.delete("/family-links/{link_id}", response_model=FamilyStaffUnlinkResponse)
def staff_unlink_family_user(
    link_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Remove one family login's access to one elder (same tenant only)."""
    return HomeSafetyFamilyService.staff_unlink_family_user(
        db, current_user, link_id=link_id, request=request
    )


@care_router.get("/family-messages", response_model=list[FamilyStaffInboxRowResponse])
def staff_family_inbox(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """One row per client with a family thread; unread = family messages since staff last read."""
    from app.core.rbac import resolve_tenant_id
    from app.core.team_scope import team_elder_ids

    rows = FamilyCareHubService.staff_inbox(db, resolve_tenant_id(current_user))
    team = team_elder_ids(db, current_user)
    if team is None:
        return rows
    return [r for r in rows if (r["elder_id"] if isinstance(r, dict) else r.elder_id) in team]


@care_router.get("/family-messages/{elder_id}", response_model=FamilyStaffThreadResponse)
def staff_family_thread(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return FamilyCareHubService.staff_thread(db, current_user, elder_id)


@care_router.post("/family-messages/{elder_id}/reply", response_model=FamilyMessageResponse)
def staff_family_reply(
    elder_id: int,
    body: FamilyMessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    elder = FamilyCareHubService._elder_for_staff(db, current_user, elder_id)
    result = FamilyCareHubService.reply_message(db, elder, current_user, body.body)
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Replied to family message",
        summary=f"Reply to family of {elder.first_name} {elder.last_name}".strip(),
        entity_type="elder",
        entity_id=str(elder_id),
        commit=True,
    )
    return result


@care_router.post("/family-messages/{elder_id}/read", response_model=FamilyStaffReadResponse)
def staff_family_mark_read(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return FamilyCareHubService.mark_staff_read(db, current_user, elder_id)


@care_router.post("/family-messages/{elder_id}/unread", response_model=FamilyStaffReadResponse)
def staff_family_mark_unread(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return FamilyCareHubService.mark_staff_unread(db, current_user, elder_id)


@care_router.get("/family-messages/{elder_id}/context")
def staff_family_thread_context(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    """One line of context above a thread: manager, next booked visit, open alerts."""
    from datetime import datetime, timezone

    from app.livewell import incident_service
    from app.models.care_job import CareJob

    elder = FamilyCareHubService._elder_for_staff(db, current_user, elder_id)
    manager = db.get(User, elder.manager_user_id) if elder.manager_user_id else None
    nxt = (
        db.query(CareJob)
        .filter(
            CareJob.elder_id == elder.id,
            CareJob.scheduled_at >= datetime.now(timezone.utc),
            CareJob.status.in_(("scheduled", "on_the_way", "checked_in")),
        )
        .order_by(CareJob.scheduled_at)
        .first()
    )
    at = nxt.scheduled_at if nxt and nxt.scheduled_at else None
    if at is not None and at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    alerts = incident_service.list_for_tenant(db, elder.tenant_id, limit=20, elder_ids={elder.id})
    return {
        "elder_id": elder.id,
        "manager_name": f"{manager.first_name or ''} {manager.last_name or ''}".strip() if manager else "",
        "next_visit_at": at.isoformat() if at else None,
        "next_visit_title": nxt.title if nxt else None,
        "open_alerts": len(alerts),
    }


@care_router.get(
    "/elders/{elder_id}/improvement-plan",
    response_model=FamilyImprovementPlanResponse,
)
def staff_get_improvement_plan(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return HomeSafetyFamilyService.staff_improvement_plan(db, current_user, elder_id)


@care_router.get(
    "/elders/{elder_id}/service-requests",
    response_model=list[FamilyServiceRequestResponse],
)
def staff_list_service_requests(
    elder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return FamilyServiceRequestService.list_for_staff(db, current_user, elder_id)


@care_router.patch(
    "/elders/{elder_id}/service-requests/{request_id}",
    response_model=FamilyServiceRequestResponse,
)
def staff_update_service_request(
    elder_id: int,
    request_id: str,
    body: FamilyServiceRequestStaffUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return FamilyServiceRequestService.staff_update(
        db,
        current_user,
        elder_id,
        request_id,
        status=body.status,
        staff_note=body.staff_note,
        quoted_amount_minor=body.quoted_amount_minor,
    )


@care_router.patch(
    "/elders/{elder_id}/plan-items/{item_id}",
    response_model=FamilyPlanItemResponse,
)
def staff_update_plan_item_status(
    elder_id: int,
    item_id: str,
    body: FamilyPlanItemStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    return HomeSafetyFamilyService.update_plan_item_status(
        db,
        current_user,
        elder_id=elder_id,
        item_id=item_id,
        status=body.status,
    )


photos_router = APIRouter(prefix="/home-safety", tags=["Safe Home — Photos"])


@photos_router.post("/photos", response_model=DocumentResponse)
async def upload_home_safety_photo(
    request: Request,
    file: UploadFile = File(...),
    prospect_id: int | None = Form(None),
    elder_id: int | None = Form(None),
    assessment_id: str | None = Form(None),
    caption: str | None = Form(None),
    room_type: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    content = await file.read()
    doc = HomeSafetyPhotoService.upload(
        db,
        current_user,
        file_name=file.filename or "photo.jpg",
        content=content,
        content_type=file.content_type or "image/jpeg",
        caption=caption,
        assessment_id=assessment_id,
        prospect_id=prospect_id,
        elder_id=elder_id,
        room_type=room_type,
    )
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Uploaded room photo",
        summary=(
            f"Uploaded {(file.filename or 'photo.jpg')}"
            + (f" · assessment {assessment_id}" if assessment_id else "")
            + (f" · room {room_type}" if room_type else "")
        ),
        entity_type="assessment" if assessment_id else "photo",
        entity_id=assessment_id or str(doc.id),
        meta={
            "document_id": doc.id,
            "room_type": room_type,
            "assessment_id": assessment_id,
        },
        commit=True,
    )
    return DocumentResponse.from_document(doc)


@photos_router.get("/photos/{document_id}/image")
def read_home_safety_photo_for_staff(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    content, mime, file_name = HomeSafetyPhotoService.read_for_staff(
        db, current_user, document_id
    )
    return Response(
        content=content,
        media_type=mime,
        headers={"Content-Disposition": f'inline; filename="{file_name}"'},
    )


from pydantic import BaseModel as _VisBaseModel  # noqa: E402


class _PhotoFamilyVisibility(_VisBaseModel):
    family_hidden: bool


@photos_router.get("/photos/{document_id}/family-visibility")
def get_photo_family_visibility(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    from app.livewell.visit_reports import photo_family_visibility

    return photo_family_visibility(db, current_user, document_id)


@photos_router.patch("/photos/{document_id}/family-visibility")
def set_photo_family_visibility(
    document_id: int,
    body: _PhotoFamilyVisibility,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Care team: hide a visit photo from the family (or show it again)."""
    from app.livewell.visit_reports import set_photo_family_hidden

    out = set_photo_family_hidden(db, current_user, document_id, body.family_hidden)
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Hid photo from family" if body.family_hidden else "Showed photo to family",
        entity_type="photo",
        entity_id=str(document_id),
        meta={"document_id": document_id, "family_hidden": body.family_hidden},
        commit=True,
    )
    return out


@router.get("/email-prefs")
def family_get_email_prefs(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """What the family gets by email, and the extra people who get it."""
    from app.livewell import email_notifications as en
    from app.models.tenant import Tenant

    elder = ElderPortalService.get_linked_elder(db, current_user)
    agency = en.get_rules(db.get(Tenant, elder.tenant_id))["family"]
    return {
        **en.get_family_prefs(elder),
        "logins": en.family_logins(db, elder),
        "events": [e for e in en.FAMILY_EVENTS if agency.get(e["key"], True)],
    }


@router.put("/email-prefs")
def family_put_email_prefs(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    from app.livewell import email_notifications as en

    elder = ElderPortalService.get_linked_elder(db, current_user)
    en.save_family_prefs(db, elder, body)
    return family_get_email_prefs(db, current_user)


@router.get("/kushlife")
def family_kushlife(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """KushLife for the family: the last 8 visits as four checks, one plain sentence, and why."""
    from app.livewell.kushlife import kushlife_view

    elder = ElderPortalService.get_linked_elder(db, current_user)
    return kushlife_view(db, elder, limit=8, staff=False)


@router.get("/kushlife/week")
def family_kushlife_week(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """Monday card: last week's visits, mood/sleep/appetite, readings, flags, next visits —
    and the care manager's weekly summary once approved (drafts are never shown)."""
    from app.livewell.kushlife_weekly import family_week

    elder = ElderPortalService.get_linked_elder(db, current_user)
    return family_week(db, elder)


@router.get("/status")
def family_status_view(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """One status (KushLife checks + what the carer noted + care level + mobility),
    shared by Home's status line, the digest and the details page."""
    from app.livewell.family_status import family_status

    return family_status(db, ElderPortalService.get_linked_elder(db, current_user))


@router.get("/score-explain")
def family_score_explain(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """'Why this score?' — how the Independence Score™ is worked out and what pulls it down."""
    from app.livewell.score_explain import explain

    return explain(db, ElderPortalService.get_linked_elder(db, current_user), staff=False)


@router.get("/journey")
def family_journey(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """Assess → fix → install → KushLife visits → reassessment, with where we are now."""
    from app.livewell.journey import journey_for_elder

    return journey_for_elder(db, ElderPortalService.get_linked_elder(db, current_user))


# --- Phase 2F: quotes (Approve & pay), My details, health-details change requests ----------
from pydantic import BaseModel as _BaseModel  # noqa: E402


class FamilyQuoteDecline(_BaseModel):
    note: str | None = None


class FamilyMyDetailsUpdate(_BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    channel: str | None = None
    timezone: str | None = None
    level: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None


class FamilyDetailsChangeCreate(_BaseModel):
    conditions: str | None = None
    allergies: str | None = None
    medicines: str | None = None
    mobility: str | None = None
    note: str | None = None


@router.get("/products")
def family_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """Everything on sale that a family can ask for — the same catalog ops sells from
    (every active product and service). Name, code, picture, description and price before
    GST; never cost or margin. Items the latest assessment suggested are flagged."""
    from app.livewell.commerce import ensure_default_products, family_product_row
    from app.models.commerce import Product

    elder = ElderPortalService.get_linked_elder(db, current_user)
    ensure_default_products(db, elder.tenant_id)
    rows = (
        db.query(Product)
        .filter(Product.tenant_id == elder.tenant_id, Product.active.is_(True))
        .order_by(Product.sort_order, Product.id)
        .all()
    )
    reasons: dict[int, list[str]] = {}
    try:
        from app.livewell.suggestions import suggestions_for_elder

        for s in suggestions_for_elder(db, elder.tenant_id, elder.id)["items"]:
            reasons[s["product_id"]] = [r["label"] for r in s["reasons"]][:3]
    except Exception:  # recommendations are an extra; the catalog must still load
        import logging

        logging.getLogger(__name__).exception("family catalog: suggestions failed for elder %s", elder.id)
    return [
        {**family_product_row(p), "recommended": p.id in reasons, "reasons": reasons.get(p.id, [])}
        for p in rows
    ]


@router.get("/quotes")
def family_quotes(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """Quotes the care team sent: lines, GST and total. Never cost or margin."""
    from app.livewell.commerce import list_family_quotes

    return list_family_quotes(db, current_user)


@router.post("/quotes/{order_id}/accept")
def family_quote_accept(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    """Approve & pay. No amount is taken from the client — the total comes from the order."""
    from app.livewell.commerce import family_accept_quote

    result = family_accept_quote(db, current_user, order_id)
    if result.get("paid"):
        SessionActivityService.record_user_action(
            db, request=request, user=current_user, action="Approved and paid a quote",
            summary=f"Quote #{order_id}", entity_type="order", entity_id=str(order_id),
            meta={"total_paise": result["quote"]["total_paise"]}, commit=True,
        )
    return result


@router.post("/quotes/{order_id}/decline")
def family_quote_decline(
    order_id: int,
    body: FamilyQuoteDecline,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    from app.livewell.commerce import family_decline_quote

    return family_decline_quote(db, current_user, order_id, body.note)


@router.get("/my-details")
def family_my_details(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    from app.livewell.family_my_details import get_my_details

    return get_my_details(db, current_user)


@router.put("/my-details")
def family_update_my_details(
    body: FamilyMyDetailsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    from app.livewell.family_my_details import update_my_details

    return update_my_details(db, current_user, body.model_dump(exclude_unset=True))


@router.post("/details-change-request", response_model=FamilyServiceRequestResponse)
def family_details_change_request(
    body: FamilyDetailsChangeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_elder_portal),
):
    from app.livewell.family_my_details import request_details_change

    return request_details_change(db, current_user, body.model_dump())
