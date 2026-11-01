from datetime import datetime

from pydantic import BaseModel, Field


class WorkflowDefinitionResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    verticals: list[str] = []
    enabled: bool = True
    trigger: dict = {}
    conditions: dict = {}
    actions: list[dict] = []


class WorkflowConfigUpdate(BaseModel):
    disabled_workflow_ids: list[str] | None = None
    channel_overrides: dict | None = None


class WorkflowConfigResponse(BaseModel):
    disabled_workflow_ids: list[str] = []
    channel_overrides: dict = {}
    workflows: list[WorkflowDefinitionResponse] = []


class WorkflowEventResponse(BaseModel):
    id: int
    tenant_id: int
    event_type: str
    entity_type: str | None
    entity_id: int | None
    payload: dict | None
    processing_result: dict | None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReplacementSuggestion(BaseModel):
    caregiver_id: int
    caregiver_name: str
    match_score: float
    reasons: list[str] = []


class ReplacementSuggestionsResponse(BaseModel):
    elder_id: int
    elder_name: str | None = None
    exclude_caregiver_id: int | None = None
    suggestions: list[ReplacementSuggestion] = []
    bench_available: int = 0


class WorkflowTaskResponse(BaseModel):
    id: int
    tenant_id: int
    workflow_id: str
    workflow_event_id: int | None
    title: str
    description: str | None
    priority: str
    status: str
    assign_roles: str | None
    metadata_json: dict | None = None
    created_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class WorkflowTaskUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(OPEN|COMPLETED|CANCELLED)$")


class WorkflowScanResponse(BaseModel):
    tenant_id: int
    events_emitted: int
    results: list[dict] = []
