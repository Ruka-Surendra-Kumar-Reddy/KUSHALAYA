from pydantic import BaseModel, Field


class CopilotAskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    tenant_id: int | None = None


class CopilotAskResponse(BaseModel):
    answer: str
    question: str
    tenant_id: int
    provider: str
    model_version: str
    data_sources: list[str]
    context_as_of: str | None = None
    suggested_follow_ups: list[str] = []
    vertical: str | None = None


class CopilotSuggestionsResponse(BaseModel):
    questions: list[str]
    azure_openai_configured: bool
