from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import ADMIN_ROLES, READ_ROLES, WRITE_ROLES, require_roles
from app.livewell.ai_provider import LocalStubProvider
from app.livewell.ai_vision_service import HomeSafetyVisionAnalysisService
from app.livewell.ai_visualization_service import HomeSafetyAIVisualizationService
from app.models.user import User
from app.schemas.ai_visualization_contracts import (
    RenderJobAccepted,
    RenderJobCallback,
    RenderJobRequest,
    RenderJobStatus,
)
from app.schemas.home_safety_ai import (
    RoomAnalyzeApiRequest,
    RoomAnalyzeApiResponse,
    VisualizationJobCreate,
    VisualizationJobCreateResponse,
    VisualizationJobGenerateForPhoto,
    VisualizationJobResponse,
    VisualizationJobReview,
)
from app.services.session_activity_service import SessionActivityService

router = APIRouter(prefix="/home-safety/ai", tags=["Safe Home — AI Visualizations"])

# Mock GPU worker surface (Contract E) — local/dev stand-in for JarvisLabs.
gpu_router = APIRouter(
    prefix="/home-safety/ai/gpu/v1",
    tags=["Safe Home — AI GPU (Contract E mock)"],
)

# In-memory mock job store for Contract E status polling (process-local).
_MOCK_GPU_JOBS: dict[str, dict] = {}


@router.get("/visualization-jobs", response_model=list[VisualizationJobResponse])
def list_visualization_jobs(
    assessment_id: str | None = Query(None),
    prospect_id: int | None = Query(None),
    status: str | None = Query(None),
    review_status: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return HomeSafetyAIVisualizationService.list_jobs(
        db,
        current_user,
        assessment_id=assessment_id,
        prospect_id=prospect_id,
        status=status,
        review_status=review_status,
        limit=limit,
    )


@router.get("/visualization-jobs/{public_id}", response_model=VisualizationJobResponse)
def get_visualization_job(
    public_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    return HomeSafetyAIVisualizationService.get_job(db, current_user, public_id)


@router.post("/visualization-jobs", response_model=VisualizationJobCreateResponse)
def create_visualization_job(
    data: VisualizationJobCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    job = HomeSafetyAIVisualizationService.create_job(
        db,
        current_user,
        assessment_id=data.assessment_id,
        room_type=data.room_type,
        package_level=data.package_level,
        source_document_id=data.source_document_id,
        approved_solution_ids=data.approved_solution_ids,
        prospect_id=data.prospect_id,
        elder_id=data.elder_id,
        origin_session_id=SessionActivityService.session_id_from_request(request),
    )
    if job.get("cache_hit"):
        msg = "Using cached concept for this photo and package."
    elif job["status"] == "needs_review" and job.get("provider") == "local_stub":
        msg = "Local concept stub ready for review."
    elif job["status"] == "queued":
        msg = "AI visualization job queued for processing."
    else:
        msg = job.get("error_message") or "AI visualization job created."
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Sent photo to AI visualization",
        summary=(
            f"Created AI job for assessment {data.assessment_id}"
            f" · photo #{data.source_document_id}"
            f" · room {data.room_type}"
            f" · package {data.package_level}"
        ),
        entity_type="assessment",
        entity_id=data.assessment_id,
        meta={
            "source_document_id": data.source_document_id,
            "room_type": data.room_type,
            "package_level": data.package_level,
            "ai_job_id": job.get("ai_job_id"),
            "status": job.get("status"),
        },
        commit=True,
    )
    return {
        "ai_job_id": job["ai_job_id"],
        "status": job["status"],
        "message": msg,
        "job": job,
        "cache_hit": bool(job.get("cache_hit")),
    }


@router.post(
    "/visualization-jobs/generate-for-photo",
    response_model=list[VisualizationJobResponse],
)
def generate_visualizations_for_photo(
    data: VisualizationJobGenerateForPhoto,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    jobs = HomeSafetyAIVisualizationService.generate_for_photo(
        db,
        current_user,
        assessment_id=data.assessment_id,
        source_document_id=data.source_document_id,
        room_type=data.room_type,
        approved_solution_ids=data.approved_solution_ids,
        tiers=data.tiers,
        only_missing=data.only_missing,
        force=data.force,
        prospect_id=data.prospect_id,
        elder_id=data.elder_id,
        approved_product_codes=data.approved_product_codes,
        product_labels=data.product_labels,
        origin_session_id=SessionActivityService.session_id_from_request(request),
    )
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Sent photo to AI visualization",
        summary=(
            f"Generated {len(jobs)} visualization job(s) for assessment {data.assessment_id}"
            f" · photo #{data.source_document_id}"
            f" · room {data.room_type}"
        ),
        entity_type="assessment",
        entity_id=data.assessment_id,
        meta={
            "source_document_id": data.source_document_id,
            "room_type": data.room_type,
            "job_count": len(jobs),
            "tiers": data.tiers,
        },
        commit=True,
    )
    return jobs


@router.post(
    "/visualization-jobs/upload-concept",
    response_model=VisualizationJobResponse,
)
async def upload_visualization_concept(
    request: Request,
    file: UploadFile = File(...),
    assessment_id: str = Form(...),
    source_document_id: int = Form(...),
    room_type: str = Form(...),
    package_level: str = Form("essential"),
    approved_solution_ids: str | None = Form(None),
    approved_product_codes: str | None = Form(None),
    product_labels: str | None = Form(None),
    prospect_id: int | None = Form(None),
    elder_id: int | None = Form(None),
    ai_job_id: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    """Upload a manual after/concept photo when AI render is missing or skipped."""
    import json

    content = await file.read()

    def _parse_str_list(raw: str | None) -> list[str]:
        if not raw or not raw.strip():
            return []
        text = raw.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except json.JSONDecodeError:
                pass
        return [s.strip() for s in text.split(",") if s.strip()]

    solution_ids = _parse_str_list(approved_solution_ids)
    product_codes = _parse_str_list(approved_product_codes)
    labels = _parse_str_list(product_labels)

    result = HomeSafetyAIVisualizationService.upload_concept_image(
        db,
        current_user,
        assessment_id=assessment_id,
        source_document_id=source_document_id,
        room_type=room_type,
        package_level=package_level,
        file_name=file.filename or "concept.jpg",
        content=content,
        content_type=file.content_type or "image/jpeg",
        approved_solution_ids=solution_ids,
        approved_product_codes=product_codes,
        product_labels=labels,
        prospect_id=prospect_id,
        elder_id=elder_id,
        ai_job_id=ai_job_id,
        origin_session_id=SessionActivityService.session_id_from_request(request),
    )
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Uploaded concept (after) photo",
        summary=(
            f"Manual concept upload for assessment {assessment_id}"
            f" · source photo #{source_document_id}"
            f" · room {room_type}"
        ),
        entity_type="assessment",
        entity_id=assessment_id,
        meta={"source_document_id": source_document_id, "room_type": room_type},
        commit=True,
    )
    return result


@router.post("/visualization-jobs/{public_id}/review", response_model=VisualizationJobResponse)
def review_visualization_job(
    public_id: str,
    data: VisualizationJobReview,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    result = HomeSafetyAIVisualizationService.review_job(
        db,
        current_user,
        public_id,
        action=data.action,
        notes=data.notes,
    )
    action_label = {
        "approve": "Approved AI visualization",
        "reject": "Rejected AI visualization",
        "needs_changes": "Requested AI visualization changes",
    }.get(str(data.action).lower(), f"Reviewed AI visualization ({data.action})")
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action=action_label,
        summary=f"Review {data.action} on AI job {public_id}",
        entity_type="ai_job",
        entity_id=public_id,
        meta={"review_action": data.action, "notes": data.notes},
        commit=True,
    )
    return result


@router.post("/analyze", response_model=RoomAnalyzeApiResponse)
def analyze_room_photos(
    data: RoomAnalyzeApiRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*WRITE_ROLES)),
):
    result = HomeSafetyVisionAnalysisService.analyze(
        db,
        current_user,
        assessment_id=data.assessment_id,
        room_type=data.room_type,
        document_ids=data.document_ids,
        force=data.force,
        origin_session_id=SessionActivityService.session_id_from_request(request),
    )
    SessionActivityService.record_user_action(
        db,
        request=request,
        user=current_user,
        action="Sent photo(s) to AI vision",
        summary=(
            f"Vision analysis for assessment {data.assessment_id}"
            f" · room {data.room_type}"
            f" · {len(data.document_ids or [])} photo(s)"
        ),
        entity_type="assessment",
        entity_id=data.assessment_id,
        meta={
            "room_type": data.room_type,
            "document_ids": data.document_ids,
            "force": data.force,
        },
        commit=True,
    )
    return result


@router.get("/analyze/{document_id}", response_model=RoomAnalyzeApiResponse)
def get_room_analysis(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*READ_ROLES)),
):
    row = HomeSafetyVisionAnalysisService.get_cached_for_document(
        db, current_user, document_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="No analysis cached for this photo")
    return row


@gpu_router.post(
    "/visualizations",
    response_model=RenderJobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def mock_gpu_submit_visualization(
    data: RenderJobRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    """Contract E mock: accept render jobs and complete via local stub."""
    del current_user
    if not data.render_items:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "UNSAFE_OR_UNSUPPORTED_PLAN",
                    "message": "Render request has no render_items",
                    "retryable": False,
                    "job_id": data.job_id,
                }
            },
        )

    key = idempotency_key or data.job_id
    if key in _MOCK_GPU_JOBS and _MOCK_GPU_JOBS[key].get("accepted"):
        response.status_code = status.HTTP_202_ACCEPTED
        return RenderJobAccepted.model_validate(_MOCK_GPU_JOBS[key]["accepted"])

    accepted = RenderJobAccepted(
        job_id=data.job_id,
        status=RenderJobStatus.QUEUED,
        status_url=f"/api/v1/home-safety/ai/gpu/v1/jobs/{data.job_id}",
        accepted_at=datetime.now(timezone.utc),
    )

    tiny_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    result = LocalStubProvider().submit_render(data, source_image_bytes=tiny_png)
    callback = result.render_callback
    if callback is None:
        callback = RenderJobCallback(
            job_id=data.job_id,
            status=RenderJobStatus.FAILED,
            completed_at=datetime.now(timezone.utc),
            error={
                "code": result.error_code or "INFERENCE_FAILED",
                "message": result.error_message,
            },
        )
    payload = {
        "accepted": accepted.model_dump(mode="json"),
        "callback": callback.model_dump(mode="json"),
        "request": data.model_dump(mode="json"),
    }
    _MOCK_GPU_JOBS[key] = payload
    _MOCK_GPU_JOBS[data.job_id] = payload
    response.status_code = status.HTTP_202_ACCEPTED
    return accepted


@gpu_router.get("/jobs/{job_id}")
def mock_gpu_job_status(
    job_id: str,
    current_user: User = Depends(require_roles(*ADMIN_ROLES)),
):
    del current_user
    row = _MOCK_GPU_JOBS.get(job_id)
    if not row:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": f"Unknown GPU job {job_id}",
                    "retryable": False,
                    "job_id": job_id,
                }
            },
        )
    return {
        "job_id": job_id,
        "accepted": row.get("accepted"),
        "result": row.get("callback"),
    }
