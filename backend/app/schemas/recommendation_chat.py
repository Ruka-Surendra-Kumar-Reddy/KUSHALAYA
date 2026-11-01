"""API + LLM structured schemas for assessor recommendation chat."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RecommendationItemOut(BaseModel):
    product_id: str | None = None
    solution_id: str | None = None
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    reason: str = ""
    linked_rubric_item_ids: list[str] = Field(default_factory=list)
    requires_human_review: bool = False
    review_reason: str | None = None


class AssessorChatLlmAnswer(BaseModel):
    """Strict schema the model must return as JSON."""

    answer: str = Field(min_length=1)
    recommendations: list[RecommendationItemOut] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    requires_human_review: bool = False
    reason_for_review: str | None = None
    cited_rubric_item_ids: list[str] = Field(default_factory=list)


class CreateConversationRequest(BaseModel):
    assessment_id: str = Field(min_length=1, max_length=64)
    title: str | None = Field(default=None, max_length=255)


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    structured: dict | None = None
    validation_status: str | None = None
    requires_human_review: bool = False
    latency_ms: float | None = None
    created_at: datetime


class ConversationSummaryOut(BaseModel):
    id: str
    assessment_id: str
    elder_id: int | None = None
    prospect_id: int | None = None
    title: str
    status: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationDetailOut(ConversationSummaryOut):
    messages: list[MessageOut] = Field(default_factory=list)


class SendMessageResponse(BaseModel):
    conversation: ConversationSummaryOut
    user_message: MessageOut
    assistant_message: MessageOut
    azure_configured: bool = True
