from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    elder_id: int
    limit: int = Field(default=10, ge=1, le=50)


class FeedbackRequest(BaseModel):
    match_result_id: int
    rating: int = Field(ge=1, le=5)
    comments: str | None = None
    decision: str | None = None


class UnstaffedAutoMatchRequest(BaseModel):
    min_score: float = Field(default=60.0, ge=0, le=100)
    limit: int = Field(default=20, ge=1, le=100)
    dry_run: bool = Field(
        default=True,
        description="Preview pairings without creating assignments",
    )


class UnstaffedMatchProposal(BaseModel):
    elder_id: int
    elder_name: str
    caregiver_id: int
    caregiver_name: str
    match_score: float
    confidence_score: float | None = None
    reasons: list[str] = Field(default_factory=list)
    schedule_days: list[str] = Field(default_factory=list)
    action: str


class UnstaffedUnmatched(BaseModel):
    elder_id: int
    elder_name: str
    reason: str


class UnstaffedAutoMatchResponse(BaseModel):
    mode: str
    uncovered_count: int
    bench_available: int
    proposed: int
    created: int
    unmatched_count: int
    proposals: list[UnstaffedMatchProposal]
    unmatched: list[UnstaffedUnmatched]
