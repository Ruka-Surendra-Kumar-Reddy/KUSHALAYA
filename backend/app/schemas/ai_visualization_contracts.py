"""Assessment-Guided AI Room Visualization — interface contracts v1.0.

Implements the LiveWell360 interface specification baseline (2026-07-16):
Contracts A (KAA output), B (recommendations), D (visualization plan),
E (async render), human review, common envelope, and error model.

Contract C (room analysis) is executed by Gemini 2.5 Flash when GEMINI_API_KEY
is configured; results are cached by photo SHA-256 and never re-billed.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


SCHEMA_VERSION = "1.0"
INTERFACE_VERSION = "2026-07-16"


# ——— Enums ———


class RoomType(str, Enum):
    BATHROOM = "BATHROOM"
    BEDROOM = "BEDROOM"
    ENTRANCE = "ENTRANCE"
    STAIRS = "STAIRS"
    HALLWAY = "HALLWAY"
    KITCHEN = "KITCHEN"
    LIVING_ROOM = "LIVING_ROOM"
    OTHER = "OTHER"


class FindingSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"
    INFO = "INFO"


class RecommendationPriority(str, Enum):
    REQUIRED = "REQUIRED"
    RECOMMENDED = "RECOMMENDED"
    OPTIONAL = "OPTIONAL"


class VisualizationMode(str, Enum):
    INSERT_OBJECT = "INSERT_OBJECT"
    REPLACE_OBJECT = "REPLACE_OBJECT"
    SURFACE_TREATMENT = "SURFACE_TREATMENT"
    LIGHTING_SIMULATION = "LIGHTING_SIMULATION"
    REMOVE_HAZARD = "REMOVE_HAZARD"
    NO_VISUALIZATION = "NO_VISUALIZATION"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED_FOR_VISUALIZATION = "APPROVED_FOR_VISUALIZATION"
    REJECTED = "REJECTED"
    NOT_VISUALIZABLE = "NOT_VISUALIZABLE"


class RenderJobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ReviewDecision(str, Enum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    REJECTED = "REJECTED"
    NOT_VISUALIZABLE = "NOT_VISUALIZABLE"
    REPOSITION = "REPOSITION"


class MeasurementStatus(str, Enum):
    MEASURED = "MEASURED"
    ESTIMATED = "ESTIMATED"
    UNAVAILABLE = "UNAVAILABLE"


# ——— Common envelope ———


class MessageEnvelope(BaseModel):
    schema_version: str = SCHEMA_VERSION
    message_id: str
    correlation_id: str
    tenant_id: str
    created_at: datetime
    producer: str
    idempotency_key: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class NormalizedBox(BaseModel):
    """Coordinates normalized 0.0–1.0, origin upper-left."""

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    width: float = Field(ge=0.0, le=1.0)
    height: float = Field(ge=0.0, le=1.0)


class Placement(BaseModel):
    anchor_x: float = Field(ge=0.0, le=1.0)
    anchor_y: float = Field(ge=0.0, le=1.0)
    orientation_degrees: float = 0.0
    estimated_length_ratio: float | None = Field(default=None, ge=0.0, le=1.0)


# ——— Contract A — KAA assessment output ———


class RoomDimensionsMm(BaseModel):
    length: int | None = None
    width: int | None = None
    height: int | None = None
    measurement_status: MeasurementStatus = MeasurementStatus.UNAVAILABLE


class AssessmentFinding(BaseModel):
    finding_id: str
    finding_code: str
    severity: FindingSeverity = FindingSeverity.MODERATE
    source_question_ids: list[str] = Field(default_factory=list)
    assessor_observation: str | None = None
    evidence_photo_ids: list[str] = Field(default_factory=list)
    requires_visualization: bool = False


class AssessmentRoom(BaseModel):
    room_id: str
    room_type: RoomType
    dimensions_mm: RoomDimensionsMm | None = None
    photo_ids: list[str] = Field(default_factory=list)
    findings: list[AssessmentFinding] = Field(default_factory=list)

    @field_validator("photo_ids")
    @classmethod
    def _require_photos_when_visualizing(cls, v: list[str]) -> list[str]:
        return v


class LwaAssessmentOutput(BaseModel):
    """Contract A — producer: KAA service."""

    schema_version: str = SCHEMA_VERSION
    assessment_id: str
    elder_id: str
    assessor_id: str | None = None
    completed_at: datetime | None = None
    independence_score: int = Field(ge=0, le=100)
    domain_scores: dict[str, int] = Field(default_factory=dict)
    rooms: list[AssessmentRoom] = Field(default_factory=list)

    @field_validator("domain_scores")
    @classmethod
    def _scores_in_range(cls, v: dict[str, int]) -> dict[str, int]:
        for key, score in v.items():
            if not 0 <= int(score) <= 100:
                raise ValueError(f"domain score out of range for {key}: {score}")
        return {str(k).upper(): int(val) for k, val in v.items()}


# ——— Contract B — Rule-engine recommendations ———


class PlacementConstraints(BaseModel):
    target_zone: str | None = None
    preferred_height_mm: int | None = None
    minimum_clearance_mm: int | None = None
    avoid_zones: list[str] = Field(default_factory=list)


class RecommendationItem(BaseModel):
    recommendation_id: str
    finding_ids: list[str] = Field(default_factory=list)
    solution_code: str
    product_code: str | None = None
    priority: RecommendationPriority = RecommendationPriority.RECOMMENDED
    visualization_mode: VisualizationMode = VisualizationMode.INSERT_OBJECT
    placement_constraints: PlacementConstraints | None = None
    human_verification: list[str] = Field(default_factory=list)
    label: str | None = None


class RoomRecommendation(BaseModel):
    room_id: str
    items: list[RecommendationItem] = Field(default_factory=list)


class RecommendationSet(BaseModel):
    """Contract B — producer: rule engine."""

    schema_version: str = SCHEMA_VERSION
    recommendation_set_id: str
    assessment_id: str
    rule_config_version: str
    room_recommendations: list[RoomRecommendation] = Field(default_factory=list)


# ——— Contract C — Room analysis (schema only; execution deferred) ———


class SourceImageRef(BaseModel):
    photo_id: str
    download_url: str
    sha256: str | None = None
    width_px: int | None = None
    height_px: int | None = None
    expires_at: datetime | None = None


class RoomAnalyzeRequest(BaseModel):
    job_id: str
    room_id: str
    room_type: RoomType
    source_images: list[SourceImageRef]
    requested_outputs: list[str] = Field(
        default_factory=lambda: ["OBJECTS", "SURFACES", "DEPTH_HINTS", "LIMITATIONS"]
    )


class RoomObservation(BaseModel):
    observation_code: str
    evidence: str | None = None
    photo_id: str | None = None
    bounding_box: NormalizedBox | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_human_verification: bool = False


class RoomSurface(BaseModel):
    surface_id: str
    type: str
    polygon: list[list[float]] = Field(default_factory=list)


class RoomAnalyzeResponse(BaseModel):
    job_id: str
    status: Literal["SUCCEEDED", "FAILED", "QUEUED", "RUNNING"] = "SUCCEEDED"
    model_versions: dict[str, str] = Field(default_factory=dict)
    observations: list[RoomObservation] = Field(default_factory=list)
    surfaces: list[RoomSurface] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


# ——— Contract D — Visualization plan ———


class RenderMask(BaseModel):
    source: Literal["SERVER_GENERATED", "ASSESSOR", "NONE"] = "NONE"
    mask_url: str | None = None
    sha256: str | None = None


class VisualizationRenderItem(BaseModel):
    render_item_id: str
    recommendation_id: str
    product_code: str | None = None
    product_asset_version: str | None = None
    operation: VisualizationMode = VisualizationMode.INSERT_OBJECT
    target_surface_id: str | None = None
    placement: Placement | None = None
    mask: RenderMask | None = None
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    label: str | None = None


class VisualizationPlan(BaseModel):
    """Contract D — only APPROVED_FOR_VISUALIZATION items may go to GPU."""

    schema_version: str = SCHEMA_VERSION
    visualization_plan_id: str
    assessment_id: str
    room_id: str
    source_photo_id: str
    source_photo_sha256: str | None = None
    recommendation_set_id: str
    assessor_approved_by: str | None = None
    assessor_approved_at: datetime | None = None
    render_items: list[VisualizationRenderItem] = Field(default_factory=list)
    preservation_constraints: list[str] = Field(
        default_factory=lambda: [
            "ROOM_GEOMETRY",
            "DOORS",
            "WINDOWS",
            "FIXED_PLUMBING",
            "EXISTING_TILES",
        ]
    )
    disclosure_required: bool = True
    package_level: str | None = None
    prompt_text: str | None = None
    negative_prompt_text: str | None = None

    def approved_items(self) -> list[VisualizationRenderItem]:
        return [
            i
            for i in self.render_items
            if i.approval_status == ApprovalStatus.APPROVED_FOR_VISUALIZATION
            and i.operation != VisualizationMode.NO_VISUALIZATION
        ]


# ——— Contract E — Async render job ———


class RenderProductRef(BaseModel):
    product_code: str
    finish: str | None = None
    reference_asset_urls: list[str] = Field(default_factory=list)


class RenderJobItem(BaseModel):
    render_item_id: str
    operation: VisualizationMode
    product: RenderProductRef | None = None
    mask_url: str | None = None
    control_image_url: str | None = None
    placement: Placement | None = None
    label: str | None = None


class GenerationProfile(BaseModel):
    profile: str = "PHOTOREALISTIC_PRESERVE_ROOM_V1"
    output_width: int = 1024
    output_height: int = 1024
    seed: int | None = None
    candidate_count: int = Field(default=1, ge=1, le=3)


class RenderCallback(BaseModel):
    url: str
    secret_ref: str | None = None


class RenderJobRequest(BaseModel):
    """Contract E — POST /gpu/v1/visualizations body."""

    job_id: str
    visualization_plan_id: str
    source_image: SourceImageRef
    render_items: list[RenderJobItem]
    generation: GenerationProfile = Field(default_factory=GenerationProfile)
    callback: RenderCallback | None = None
    # Orchestrator-only helpers for local stub (never sent to remote GPU with PII)
    prompt_text: str | None = None
    negative_prompt_text: str | None = None
    room_type: str | None = None
    package_level: str | None = None


class RenderJobAccepted(BaseModel):
    job_id: str
    status: RenderJobStatus = RenderJobStatus.QUEUED
    status_url: str
    accepted_at: datetime


class QualityScores(BaseModel):
    room_preservation_score: float | None = Field(default=None, ge=0.0, le=1.0)
    placement_score: float | None = Field(default=None, ge=0.0, le=1.0)
    artifact_score: float | None = Field(default=None, ge=0.0, le=1.0)


class RenderOutputCandidate(BaseModel):
    candidate_id: str
    image_url: str | None = None
    image_bytes_b64: str | None = None
    content_type: str | None = "image/png"
    sha256: str | None = None
    width_px: int | None = None
    height_px: int | None = None
    quality: QualityScores | None = None
    review_required: bool = True


class RenderProvenance(BaseModel):
    model_set_version: str | None = None
    prompt_template_version: str | None = None
    seed: int | None = None
    gpu_type: str | None = None
    provider: str | None = None
    is_stub: bool = False


class RenderJobCallback(BaseModel):
    job_id: str
    status: RenderJobStatus
    completed_at: datetime | None = None
    outputs: list[RenderOutputCandidate] = Field(default_factory=list)
    provenance: RenderProvenance | None = None
    error: dict[str, Any] | None = None


# ——— Human review ———


class ItemReview(BaseModel):
    render_item_id: str
    decision: ReviewDecision
    corrected_placement: Placement | None = None
    comment_code: str | None = None
    comment: str | None = None


class VisualizationReviewRequest(BaseModel):
    candidate_id: str
    decision: ReviewDecision
    reviewer_id: str
    item_reviews: list[ItemReview] = Field(default_factory=list)
    notes: str | None = None


class VisualizationReviewResponse(BaseModel):
    job_id: str
    candidate_id: str
    decision: ReviewDecision
    reviewed_at: datetime
    next_action: Literal[
        "PUBLISH",
        "REGENERATE",
        "SUPPRESS",
        "KEEP_WRITTEN_ONLY",
    ]


# ——— Error model ———


class ContractErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool = False
    retry_after_seconds: int | None = None
    job_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ContractErrorResponse(BaseModel):
    error: ContractErrorBody


# ——— Orchestrator bundle (A→B→D→E) ———


class VisualizationContractBundle(BaseModel):
    """Convenience aggregate used by the LiveWell360 orchestrator."""

    schema_version: str = SCHEMA_VERSION
    interface_version: str = INTERFACE_VERSION
    assessment: LwaAssessmentOutput
    recommendations: RecommendationSet
    plan: VisualizationPlan
    render_request: RenderJobRequest | None = None
