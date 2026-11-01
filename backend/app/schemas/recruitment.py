from pydantic import BaseModel, Field


class ParsedResumeFields(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    years_experience: int | None = None
    languages: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    work_history: list[dict] = Field(default_factory=list)
    care_types: list[str] = Field(default_factory=list)
    summary: str | None = None


class ResumeParseResponse(BaseModel):
    provider: str
    model: str | None = None
    text_provider: str | None = None
    confidence: str
    candidate_score: float
    score_reasons: list[str] = Field(default_factory=list)
    fields: ParsedResumeFields
    raw_text_preview: str
    extracted_at: str


class ResumeAttachResponse(BaseModel):
    prospect: dict
    parse: ResumeParseResponse
    document_id: int


class PlacementSuggestion(BaseModel):
    elder_id: int
    elder_name: str
    match_score: float
    reasons: list[str] = Field(default_factory=list)
    uncovered: bool = False
    care_level: str | None = None


class PlacementSuggestionsResponse(BaseModel):
    prospect_id: int
    prospect_name: str
    resume_score: float | None = None
    uncovered_clients: int = 0
    suggestions: list[PlacementSuggestion] = Field(default_factory=list)
