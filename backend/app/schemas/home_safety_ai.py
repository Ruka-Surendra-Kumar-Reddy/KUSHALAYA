from datetime import datetime

from pydantic import BaseModel, Field


class VisualizationJobCreate(BaseModel):
    assessment_id: str = Field(..., min_length=1, max_length=64)
    room_type: str = Field(..., min_length=1, max_length=32)
    package_level: str = Field(..., min_length=1, max_length=32)
    source_document_id: int
    approved_solution_ids: list[str] = Field(default_factory=list)
    prospect_id: int | None = None
    elder_id: int | None = None


class VisualizationJobReview(BaseModel):
    action: str = Field(..., pattern="^(approve|reject|regenerate)$")
    notes: str | None = None


class VisualizationJobGenerateForPhoto(BaseModel):
    assessment_id: str = Field(..., min_length=1, max_length=64)
    source_document_id: int
    room_type: str = Field(..., min_length=1, max_length=32)
    approved_solution_ids: list[str] = Field(default_factory=list)
    # Catalog products the assessor picked for the after/concept image.
    approved_product_codes: list[str] = Field(default_factory=list)
    product_labels: list[str] = Field(default_factory=list)
    tiers: list[str] | None = None
    only_missing: bool = True
    # When False, reuse a successful concept for the same photo+tier+solutions+provider.
    force: bool = False
    prospect_id: int | None = None
    elder_id: int | None = None


class RoomAnalyzeApiRequest(BaseModel):
    assessment_id: str = Field(..., min_length=1, max_length=64)
    room_type: str = Field(..., min_length=1, max_length=32)
    document_ids: list[int] = Field(..., min_length=1)
    force: bool = False


class RoomAnalyzeMappedSuggestion(BaseModel):
    finding_code: str
    solution_id: str | None = None
    confidence: float = 0.0
    confidence_percent: int = 0
    evidence: str | None = None
    photo_id: str | None = None
    requires_human_verification: bool = True
    auto_apply_eligible: bool = False


class RoomAnalyzeApiResponse(BaseModel):
    id: int
    assessment_id: str | None = None
    document_id: int
    room_type: str | None = None
    sha256: str
    provider: str
    model_version: str
    status: str
    response: dict = Field(default_factory=dict)
    mapped_suggestions: list[RoomAnalyzeMappedSuggestion] = Field(default_factory=list)
    error_message: str | None = None
    cache_hit: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class VisualizationJobResponse(BaseModel):
    ai_job_id: str
    id: int
    assessment_id: str
    prospect_id: int | None = None
    elder_id: int | None = None
    room_type: str
    package_level: str
    source_document_id: int
    status: str
    provider: str | None = None
    provider_job_id: str | None = None
    original_image_url: str | None = None
    generated_document_id: int | None = None
    generated_image_url: str | None = None
    prompt_text: str | None = None
    negative_prompt_text: str | None = None
    workflow_name: str | None = None
    workflow_version: int | None = None
    model_name: str | None = None
    approved_solution_ids: list[str] = Field(default_factory=list)
    generation_time_seconds: int | None = None
    retry_count: int = 0
    error_code: str | None = None
    error_message: str | None = None
    review_status: str
    reviewed_by_user_id: int | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None
    created_at: datetime
    updated_at: datetime
    event_log: list[dict] = Field(default_factory=list)
    visualization_plan_id: str | None = None
    recommendation_set_id: str | None = None
    render_job_id: str | None = None
    current_phase: str | None = None
    phase_snapshot: dict | None = None
    render_callback: dict | None = None
    cache_hit: bool = False


class VisualizationJobCreateResponse(BaseModel):
    ai_job_id: str
    status: str
    message: str
    job: VisualizationJobResponse
    cache_hit: bool = False
