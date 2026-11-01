from datetime import datetime

from pydantic import BaseModel, Field


class SessionEventResponse(BaseModel):
    id: int
    session_id: str
    occurred_at: datetime
    event_kind: str
    action: str
    method: str | None = None
    path: str | None = None
    status_code: int | None = None
    duration_ms: float | None = None
    request_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    summary: str | None = None
    meta: dict | None = None

    model_config = {"from_attributes": True}


class SessionSummaryResponse(BaseModel):
    id: str
    tenant_id: int | None = None
    user_id: int
    actor_type: str
    user_email: str
    user_name: str
    user_role: str
    started_at: datetime
    last_seen_at: datetime
    ended_at: datetime | None = None
    user_agent: str | None = None
    ip_address: str | None = None
    event_count: int = 0
    # Latest plain actions ("Edited Lakshmi Reddy · assessor"), so a row says what changed.
    recent_actions: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SessionDetailResponse(SessionSummaryResponse):
    events: list[SessionEventResponse] = Field(default_factory=list)
