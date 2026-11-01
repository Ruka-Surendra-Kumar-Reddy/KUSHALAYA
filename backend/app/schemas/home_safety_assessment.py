from pydantic import BaseModel, Field


class HomeSafetyAssessmentPayload(BaseModel):
    """Client assessment document (matches frontend HomeSafetyAssessment)."""

    id: str
    createdAt: str
    updatedAt: str
    completedAt: str | None = None
    status: str = "draft"
    frameworkVersion: str | None = None
    clientFirstName: str = ""
    clientLastName: str = ""
    clientAddress: str = ""
    clientPhone: str = ""
    clientEmail: str = ""
    familyContactName: str = ""
    familyContactPhone: str = ""
    painPoints: str = ""
    assessorName: str = ""
    notes: str = ""
    residentProfile: dict = Field(default_factory=dict)
    ratings: dict = Field(default_factory=dict)
    itemNotes: dict = Field(default_factory=dict)
    prospectId: int | None = None
    prospectSyncedAt: str | None = None
    elderId: int | None = None
    photos: list[dict] = Field(default_factory=list)
    purchaseOrder: dict | None = None
    independenceScore: int | None = None
    familyImprovementPlan: dict | None = None
    familyScoreSummary: str | None = None
    familyDomainScores: list | None = None
    familyCarePathway: dict | None = None
    familyShareBrief: str | None = None
    # Server-scored on completion (see app/livewell/scoring.py). The client may
    # send them; the server overwrites them for completed assessments.
    domainScores: dict | None = None
    criticalFindings: list | None = None
    clientReportedScore: int | None = None
    scoringSource: str | None = None
    serverScoredAt: str | None = None
    # Rule-engine stamps (assessment_service._stamp_rule_recommendations).
    recommended_membership_id: str | None = None
    ecm_recommended: bool | None = None
    risk_band: str | None = None
    risk_band_label: str | None = None
    risk_escalation_level: str | None = None
    ruleEngineSource: str | None = None
    # Transient: a completed assessment is locked; the client must send
    # reopen=true to change its content. Never stored.
    reopen: bool | None = None


class HomeSafetyAssessmentSummary(BaseModel):
    assessment_id: str
    status: str
    client_first_name: str = ""
    client_last_name: str = ""
    client_address: str = ""
    updated_at: str
    completed_at: str | None = None
    prospect_id: int | None = None
    elder_id: int | None = None
    # Only with ?full=true: the whole assessment, so the list needs one request, not one per row.
    payload: dict | None = None


class HomeSafetyAssessmentResponse(BaseModel):
    assessment_id: str
    status: str
    payload: HomeSafetyAssessmentPayload
    updated_at: str
    completed_at: str | None = None
    locked: bool = False
    server_score: int | None = None
    client_reported_score: int | None = None
    versions: list[dict] = Field(default_factory=list)
