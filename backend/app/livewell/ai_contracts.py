"""Builders and adapters for AI visualization contracts A/B/D/E."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any

from app.schemas.ai_visualization_contracts import (
    SCHEMA_VERSION,
    ApprovalStatus,
    AssessmentFinding,
    AssessmentRoom,
    FindingSeverity,
    GenerationProfile,
    LwaAssessmentOutput,
    MeasurementStatus,
    PlacementConstraints,
    RecommendationItem,
    RecommendationPriority,
    RecommendationSet,
    RenderCallback,
    RenderJobItem,
    RenderJobRequest,
    RenderProductRef,
    RoomDimensionsMm,
    RoomRecommendation,
    RoomType,
    SourceImageRef,
    VisualizationContractBundle,
    VisualizationMode,
    VisualizationPlan,
    VisualizationRenderItem,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def map_room_type(raw: str | None) -> RoomType:
    key = (raw or "OTHER").strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "ENTRY": RoomType.ENTRANCE,
        "ENTRANCE": RoomType.ENTRANCE,
        "BATH": RoomType.BATHROOM,
        "BATHROOM": RoomType.BATHROOM,
        "BED": RoomType.BEDROOM,
        "BEDROOM": RoomType.BEDROOM,
        "HALL": RoomType.HALLWAY,
        "HALLWAY": RoomType.HALLWAY,
        "KITCHEN": RoomType.KITCHEN,
        "LIVING": RoomType.LIVING_ROOM,
        "LIVING_ROOM": RoomType.LIVING_ROOM,
        "STAIR": RoomType.STAIRS,
        "STAIRS": RoomType.STAIRS,
    }
    return aliases.get(key, RoomType.OTHER)


def sha256_hex(data: bytes | None) -> str | None:
    if not data:
        return None
    return hashlib.sha256(data).hexdigest()


def build_assessment_output(
    *,
    assessment_id: str,
    elder_id: str | int | None,
    assessor_id: str | int | None = None,
    independence_score: int | None = None,
    domain_scores: dict[str, int] | None = None,
    room_type: str,
    photo_ids: list[str],
    finding_codes: list[str] | None = None,
    completed_at: datetime | None = None,
    assessment_payload: dict[str, Any] | None = None,
) -> LwaAssessmentOutput:
    """Contract A — from current assessment / job context."""
    payload = assessment_payload or {}
    score = independence_score
    if score is None:
        raw = payload.get("independenceScore") or payload.get("independence_score")
        score = int(raw) if raw is not None else 0
    domains = domain_scores or {}
    if not domains and isinstance(payload.get("domainScores"), dict):
        domains = {str(k): int(v) for k, v in payload["domainScores"].items()}
    if not domains and isinstance(payload.get("familyDomainScores"), list):
        # Frontend stamps familyDomainScores (list of {id, score}); domainScores
        # (dict) is the server-scored form — accept either.
        domains = {
            str(row.get("id")): int(row.get("score") or 0)
            for row in payload["familyDomainScores"]
            if isinstance(row, dict) and row.get("id") is not None
        }

    room_id = f"ROOM-{map_room_type(room_type).value[:4]}-01"
    findings: list[AssessmentFinding] = []
    for i, code in enumerate(finding_codes or []):
        code_s = str(code).strip()
        if not code_s:
            continue
        findings.append(
            AssessmentFinding(
                finding_id=f"FND-{i + 1:04d}",
                finding_code=code_s.upper().replace(" ", "_"),
                severity=FindingSeverity.HIGH,
                source_question_ids=[],
                requires_visualization=True,
                evidence_photo_ids=list(photo_ids[:1]),
            )
        )
    if not findings and photo_ids:
        # Synthetic finding so visualization plans remain rule-gated downstream.
        findings.append(
            AssessmentFinding(
                finding_id="FND-0001",
                finding_code="ASSESSMENT_APPROVED_MODIFICATIONS",
                severity=FindingSeverity.MODERATE,
                requires_visualization=True,
                evidence_photo_ids=list(photo_ids[:1]),
                assessor_observation="Approved solutions selected for visualization",
            )
        )

    room = AssessmentRoom(
        room_id=room_id,
        room_type=map_room_type(room_type),
        dimensions_mm=RoomDimensionsMm(measurement_status=MeasurementStatus.UNAVAILABLE),
        photo_ids=list(photo_ids),
        findings=findings,
    )
    return LwaAssessmentOutput(
        schema_version=SCHEMA_VERSION,
        assessment_id=assessment_id,
        elder_id=str(elder_id or "ELD-UNKNOWN"),
        assessor_id=str(assessor_id) if assessor_id is not None else None,
        completed_at=completed_at or _utc_now(),
        independence_score=max(0, min(100, int(score))),
        domain_scores=domains,
        rooms=[room],
    )


def build_recommendation_set(
    *,
    assessment: LwaAssessmentOutput,
    approved_solution_ids: list[str],
    modification_labels: list[str] | None = None,
    rule_config_version: str = "local",
    product_codes: dict[str, str] | None = None,
) -> RecommendationSet:
    """Contract B — map approved solutions to recommendation items."""
    room = assessment.rooms[0] if assessment.rooms else None
    room_id = room.room_id if room else "ROOM-OTHER-01"
    finding_ids = [f.finding_id for f in (room.findings if room else [])]
    labels = modification_labels or []
    product_codes = product_codes or {}
    items: list[RecommendationItem] = []
    for i, sid in enumerate(dict.fromkeys(approved_solution_ids)):
        sid_s = str(sid).strip()
        if not sid_s:
            continue
        label = labels[i] if i < len(labels) else sid_s
        items.append(
            RecommendationItem(
                recommendation_id=f"REC-{i + 1:04d}",
                finding_ids=finding_ids[:1] or ["FND-0001"],
                solution_code=sid_s.upper().replace(" ", "_"),
                product_code=product_codes.get(sid_s),
                priority=RecommendationPriority.REQUIRED if i == 0 else RecommendationPriority.RECOMMENDED,
                visualization_mode=VisualizationMode.INSERT_OBJECT,
                placement_constraints=PlacementConstraints(
                    target_zone="PRIMARY_WALL",
                    avoid_zones=["WINDOW", "MIRROR", "PLUMBING_UNKNOWN"],
                ),
                human_verification=["WALL_SUBSTRATE", "ANCHORING", "FINAL_HEIGHT"],
                label=label,
            )
        )
    if not items:
        items.append(
            RecommendationItem(
                recommendation_id="REC-0001",
                finding_ids=finding_ids[:1] or ["FND-0001"],
                solution_code="GENERAL_SENIOR_SAFETY",
                priority=RecommendationPriority.RECOMMENDED,
                visualization_mode=VisualizationMode.INSERT_OBJECT,
                label="General senior safety improvements per assessment",
            )
        )
    return RecommendationSet(
        recommendation_set_id=_new_id("RECSET"),
        assessment_id=assessment.assessment_id,
        rule_config_version=rule_config_version,
        room_recommendations=[RoomRecommendation(room_id=room_id, items=items)],
    )


def build_visualization_plan(
    *,
    assessment: LwaAssessmentOutput,
    recommendations: RecommendationSet,
    source_photo_id: str,
    source_photo_sha256: str | None = None,
    assessor_id: str | None = None,
    package_level: str | None = None,
    prompt_text: str | None = None,
    negative_prompt_text: str | None = None,
    auto_approve: bool = True,
) -> VisualizationPlan:
    """Contract D — merge recommendations into an assessor-approved plan."""
    room_rec = (
        recommendations.room_recommendations[0]
        if recommendations.room_recommendations
        else None
    )
    room_id = room_rec.room_id if room_rec else (
        assessment.rooms[0].room_id if assessment.rooms else "ROOM-OTHER-01"
    )
    render_items: list[VisualizationRenderItem] = []
    for i, item in enumerate(room_rec.items if room_rec else []):
        if item.visualization_mode == VisualizationMode.NO_VISUALIZATION:
            status = ApprovalStatus.NOT_VISUALIZABLE
        elif auto_approve:
            status = ApprovalStatus.APPROVED_FOR_VISUALIZATION
        else:
            status = ApprovalStatus.PENDING
        render_items.append(
            VisualizationRenderItem(
                render_item_id=f"RITEM-{i + 1:02d}",
                recommendation_id=item.recommendation_id,
                product_code=item.product_code or item.solution_code,
                product_asset_version="1",
                operation=item.visualization_mode,
                approval_status=status,
                label=item.label,
            )
        )
    return VisualizationPlan(
        visualization_plan_id=_new_id("VPLAN"),
        assessment_id=assessment.assessment_id,
        room_id=room_id,
        source_photo_id=source_photo_id,
        source_photo_sha256=source_photo_sha256,
        recommendation_set_id=recommendations.recommendation_set_id,
        assessor_approved_by=assessor_id,
        assessor_approved_at=_utc_now() if auto_approve else None,
        render_items=render_items,
        disclosure_required=True,
        package_level=package_level,
        prompt_text=prompt_text,
        negative_prompt_text=negative_prompt_text,
    )


def build_render_job_request(
    *,
    plan: VisualizationPlan,
    download_url: str,
    job_id: str | None = None,
    width: int = 1024,
    height: int = 1024,
    seed: int | None = None,
    callback_url: str | None = None,
) -> RenderJobRequest:
    """Contract E — only approved render items."""
    approved = plan.approved_items()
    if not approved:
        raise ValueError("UNSAFE_OR_UNSUPPORTED_PLAN: no approved render items")
    items: list[RenderJobItem] = []
    for item in approved:
        product = None
        if item.product_code:
            product = RenderProductRef(product_code=item.product_code)
        items.append(
            RenderJobItem(
                render_item_id=item.render_item_id,
                operation=item.operation,
                product=product,
                placement=item.placement,
                label=item.label,
                mask_url=item.mask.mask_url if item.mask else None,
            )
        )
    jid = job_id or _new_id("JOB-RENDER")
    return RenderJobRequest(
        job_id=jid,
        visualization_plan_id=plan.visualization_plan_id,
        source_image=SourceImageRef(
            photo_id=plan.source_photo_id,
            download_url=download_url,
            sha256=plan.source_photo_sha256,
            expires_at=None,
        ),
        render_items=items,
        generation=GenerationProfile(
            profile="PHOTOREALISTIC_PRESERVE_ROOM_V1",
            output_width=width,
            output_height=height,
            seed=seed,
            candidate_count=1,
        ),
        callback=(
            RenderCallback(url=callback_url, secret_ref="CALLBACK-KEY-LOCAL")
            if callback_url
            else None
        ),
        prompt_text=plan.prompt_text,
        negative_prompt_text=plan.negative_prompt_text,
        room_type=None,
        package_level=plan.package_level,
    )


def build_contract_bundle(
    *,
    assessment_id: str,
    elder_id: str | int | None,
    assessor_id: str | int | None,
    room_type: str,
    photo_id: str,
    download_url: str,
    approved_solution_ids: list[str],
    modification_labels: list[str] | None = None,
    source_image_bytes: bytes | None = None,
    independence_score: int | None = None,
    domain_scores: dict[str, int] | None = None,
    package_level: str | None = None,
    prompt_text: str | None = None,
    negative_prompt_text: str | None = None,
    rule_config_version: str = "local",
    width: int = 1024,
    height: int = 1024,
    job_id: str | None = None,
    assessment_payload: dict[str, Any] | None = None,
) -> VisualizationContractBundle:
    """Build A → B → D → E from orchestrator context."""
    assessment = build_assessment_output(
        assessment_id=assessment_id,
        elder_id=elder_id,
        assessor_id=assessor_id,
        independence_score=independence_score,
        domain_scores=domain_scores,
        room_type=room_type,
        photo_ids=[photo_id],
        finding_codes=list(approved_solution_ids),
        assessment_payload=assessment_payload,
    )
    recommendations = build_recommendation_set(
        assessment=assessment,
        approved_solution_ids=approved_solution_ids,
        modification_labels=modification_labels,
        rule_config_version=rule_config_version,
    )
    plan = build_visualization_plan(
        assessment=assessment,
        recommendations=recommendations,
        source_photo_id=photo_id,
        source_photo_sha256=sha256_hex(source_image_bytes),
        assessor_id=str(assessor_id) if assessor_id is not None else None,
        package_level=package_level,
        prompt_text=prompt_text,
        negative_prompt_text=negative_prompt_text,
        auto_approve=True,
    )
    # Attach room_type onto render request via package metadata
    render_request = build_render_job_request(
        plan=plan,
        download_url=download_url,
        job_id=job_id,
        width=width,
        height=height,
    )
    render_request.room_type = map_room_type(room_type).value
    render_request.package_level = package_level
    return VisualizationContractBundle(
        assessment=assessment,
        recommendations=recommendations,
        plan=plan,
        render_request=render_request,
    )
