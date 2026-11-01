from datetime import datetime

from pydantic import BaseModel, Field


class SafetyScoreResponse(BaseModel):
    total: int
    max_total: int
    grade: str
    grade_label: str
    assessed_at: datetime | None
    summary: str | None
    band_status: str | None = None
    is_demo: bool = False
    has_published_score: bool = False
    urgent_fix_count: int = 0
    critical_findings: list[dict] = Field(default_factory=list)
    domain_scores: list["FamilyDomainScoreResponse"] = Field(default_factory=list)
    care_pathway: "FamilyCarePathwayResponse | None" = None


class ScoreHistoryPointResponse(BaseModel):
    total: int
    grade: str = ""
    assessed_at: datetime | None = None
    assessment_id: str | None = None


class StabilityScorePointResponse(BaseModel):
    score: int
    visited_at: datetime | None = None
    visit_id: str | None = None
    delta_from_baseline: int | None = None
    band: str | None = None


class FamilyDomainScoreResponse(BaseModel):
    id: str
    title: str
    score: int
    max_points: int = 0
    earned_points: float = 0


class FamilyCarePathwayResponse(BaseModel):
    membership_id: str | None = None
    membership_label: str | None = None
    ecm_recommended: bool = False
    ecm_note: str | None = None


class FamilyPlanItemResponse(BaseModel):
    id: str
    title: str
    priority: str
    why: str | None = None
    actions: list[str] = Field(default_factory=list)
    score_gain: int = 0
    status: str = "open"
    domain: str | None = None
    estimated_cost: str | None = None


class FamilyPlanItemStatusUpdate(BaseModel):
    status: str


class FamilyImprovementPlanResponse(BaseModel):
    assessment_id: str | None = None
    current_score: int | None = None
    projected_score: int | None = None
    finding_count: int = 0
    published_at: datetime | None = None
    items: list[FamilyPlanItemResponse] = Field(default_factory=list)
    has_plan: bool = False
    estimated_cost_note: str | None = None


class FamilyShareBriefResponse(BaseModel):
    text: str
    senior_name: str


class FamilyApprovedVisualResponse(BaseModel):
    id: str
    room_type: str | None = None
    package_level: str | None = None
    label: str
    before_document_id: int
    after_document_id: int
    before_url: str
    after_url: str
    reviewed_at: datetime | None = None
    assessment_id: str | None = None
    product_labels: list[str] = Field(default_factory=list)
    product_codes: list[str] = Field(default_factory=list)


class WellnessReportResponse(BaseModel):
    id: str
    date: datetime
    visit_type: str
    summary: str
    assessor_name: str | None
    highlights: list[str]
    family_message: str | None = None


class FamilyVisitResponse(BaseModel):
    id: str
    visit_type: str
    visited_at: datetime
    staff_name: str | None
    partner_id: str | None = None
    partner_name: str | None = None
    summary: str
    wellness_notes: str
    family_message: str | None = None
    concerns: list[str]
    recommendations: str
    photo_ids: list[int]
    photo_urls: list[str]
    duration_minutes: int | None
    status: str
    experience_rating: int | None = None
    experience_comment: str | None = None
    rated_at: datetime | None = None
    can_rate: bool = False
    checkin: dict | None = None
    voice_notes: list[dict] = Field(default_factory=list)  # #100: only notes shared with the family
    photos: list[dict] = Field(default_factory=list)  # [{id, caption, taken_at, url}] — this elder's photos only
    # Care-job visits: when the caregiver checked in and finished (family report).
    checked_in_at: datetime | None = None
    checked_out_at: datetime | None = None


class CareStatusSnapshotResponse(BaseModel):
    overall: str | None = None
    mood: str | None = None
    mobility: str | None = None
    eating: str | None = None
    medication: str | None = None
    falls: str | None = None
    home_safety: str | None = None
    open_request: str | None = None
    staff_name: str | None = None
    care_manager_note: str | None = None
    family_message: str | None = None


class FamilyCareStatusResponse(BaseModel):
    level: str
    label: str
    headline: str
    headline_suffix: str = ""
    senior_first_name: str = ""
    reasons: list[str] = Field(default_factory=list)
    confirmed_at: datetime | None = None
    snapshot: CareStatusSnapshotResponse | None = None
    change_summary: str = ""
    open_service_requests: int = 0
    open_incidents: int = 0
    disclaimer: str = ""
    computed_at: datetime | None = None
    stability_score: int | None = None
    stability_delta_from_baseline: int | None = None
    stability_band: str | None = None


class FamilyPhotoResponse(BaseModel):
    id: int
    caption: str
    url: str | None
    taken_at: datetime
    source: str | None = None


class FamilyAlertResponse(BaseModel):
    id: str
    title: str
    body: str
    severity: str = "info"
    read_at: datetime | None
    created_at: datetime


class FamilyMessageResponse(BaseModel):
    id: str
    body: str
    sender_role: str
    sender_name: str
    created_at: datetime


class FamilyMessageCreate(BaseModel):
    body: str


class FamilyIncidentResponse(BaseModel):
    id: str
    kind: str
    note: str
    status: str
    created_at: datetime
    resolved_at: datetime | None = None
    resolved_by: str | None = None


class FamilySosCreate(BaseModel):
    note: str | None = None


class FamilyIncidentResolve(BaseModel):
    """Close an open care-hub incident (SOS / wearable)."""

    status: str = "resolved"


class FamilyDigestPrefsResponse(BaseModel):
    digest_enabled: bool = True
    digest_channel: str = "whatsapp"
    digest_cadence: str = "weekly"
    digest_timezone: str = "Asia/Kolkata"


class FamilyDigestPrefsUpdate(BaseModel):
    digest_enabled: bool | None = None
    digest_channel: str | None = None
    digest_cadence: str | None = None
    digest_timezone: str | None = None


class FamilyDigestPreviewResponse(BaseModel):
    text: str
    prefs: FamilyDigestPrefsResponse
    senior_name: str


class FamilyCareFeedItemResponse(BaseModel):
    id: str
    kind: str
    title: str
    body: str
    created_at: datetime | None = None
    href: str | None = None
    photos: list[dict] = Field(default_factory=list)  # visits only: up to 4 of this elder's photos
    photo_count: int = 0  # all family-visible photos on the visit (for "+N more")


class FamilyCircleMemberResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    portal_relationship: str
    is_you: bool = False
    is_primary: bool = False


class FamilyCircleRemoveResponse(BaseModel):
    id: int
    email: str
    removed: bool = True


class FamilyStaffUnlinkResponse(BaseModel):
    link_id: int
    user_id: int
    elder_id: int
    removed: bool = True


class FamilyStaffInboxRowResponse(BaseModel):
    elder_id: int
    elder_name: str
    message_count: int = 0
    unread_count: int = 0
    staff_read_at: datetime | None = None
    last_message: "FamilyMessageResponse"


class FamilyStaffThreadResponse(BaseModel):
    elder_id: int
    elder_name: str
    staff_read_at: datetime | None = None
    unread_count: int = 0
    messages: list["FamilyMessageResponse"] = Field(default_factory=list)


class FamilyStaffReadResponse(BaseModel):
    elder_id: int
    staff_read_at: datetime | None = None
    unread_count: int = 0


class FamilyCircleInviteRequest(BaseModel):
    email: str
    #: Optional: without it the invitee gets a set-password link by email / WhatsApp.
    password: str | None = None
    phone: str | None = None
    first_name: str = "Family"
    last_name: str = "Member"
    portal_relationship: str = "family"
    #: The senior the invite is for (the one selected in the app). Defaults to the active one.
    elder_id: int | None = None


class FamilyDocumentResponse(BaseModel):
    id: int
    title: str
    document_type: str
    created_at: datetime | None = None
    url: str
    uploaded_by_family: bool = False


class FamilyDocumentTypeResponse(BaseModel):
    id: str
    label: str


class FamilyScheduleResponse(BaseModel):
    upcoming: list[FamilyVisitResponse] = Field(default_factory=list)
    recent: list[FamilyVisitResponse] = Field(default_factory=list)


class FamilyServiceTypeResponse(BaseModel):
    id: str
    label: str
    group: str = "service"


class FamilyServiceRequestResponse(BaseModel):
    id: str
    service_type: str
    service_label: str
    group: str = "service"
    product_name: str = ""
    product_id: int | None = None
    product_code: str = ""
    items: list[dict] = []
    preferred_at: datetime | None = None
    notes: str = ""
    status: str
    created_at: datetime | None = None
    created_by: str | None = None
    staff_note: str | None = None
    visit_id: str | None = None
    quoted_amount_minor: int = 0
    quoted_amount_display: str | None = None
    payment_status: str = "not_required"
    updated_at: datetime | None = None


class FamilyServiceRequestCreate(BaseModel):
    service_type: str
    preferred_at: datetime | None = None
    notes: str | None = None
    product_name: str | None = None
    # A catalog item (GET /products): the server fills in its name and code.
    product_id: int | None = None


class FamilyServiceRequestStaffUpdate(BaseModel):
    status: str
    staff_note: str | None = None
    # Quoting a price moves the request to "awaiting_approval" for the family.
    quoted_amount_minor: int | None = None


class EmergencyContactResponse(BaseModel):
    name: str
    phone: str | None
    relationship: str | None
    is_primary: bool = False


class FamilyLinkedElderResponse(BaseModel):
    id: int
    name: str
    address: str | None = None
    is_active: bool = False
    has_published_score: bool = False
    score_total: int | None = None


class FamilyEldersListResponse(BaseModel):
    active_elder_id: int | None = None
    elders: list[FamilyLinkedElderResponse] = Field(default_factory=list)
    senior_name: str | None = None


class FamilyActiveElderRequest(BaseModel):
    elder_id: int


class FamilyStaffLinkRequest(BaseModel):
    email: str
    set_active: bool = False


class FamilyStaffLinkResponse(BaseModel):
    user_id: int
    email: str
    active_elder_id: int | None = None
    elders: list[FamilyLinkedElderResponse] = Field(default_factory=list)


class FamilyDashboardResponse(BaseModel):
    parent_name: str
    viewer_first_name: str | None = None
    viewer_is_elder: bool = False
    senior_name: str
    senior_address: str | None
    safety: SafetyScoreResponse
    unread_alerts: int
    last_visit_at: datetime | None
    wellness_count: int
    visit_count: int = 0
    has_published_score: bool = False
    top_priorities: list[FamilyPlanItemResponse] = Field(default_factory=list)
    plan_item_count: int = 0
    projected_score: int | None = None
    stability_score_history: list[StabilityScorePointResponse] = Field(default_factory=list)
    stability_score_delta: int | None = None
    latest_stability_score: int | None = None
    approved_visual_count: int = 0
    preview_visuals: list[FamilyApprovedVisualResponse] = Field(default_factory=list)
    domain_scores: list[FamilyDomainScoreResponse] = Field(default_factory=list)
    care_pathway: FamilyCarePathwayResponse | None = None
    share_brief: str | None = None
    estimated_cost_note: str | None = None
    next_visit_at: datetime | None = None
    next_visit_label: str | None = None
    open_incidents: int = 0
    unread_messages_hint: int = 0
    active_elder_id: int | None = None
    elders: list[FamilyLinkedElderResponse] = Field(default_factory=list)
    care_status: FamilyCareStatusResponse | None = None
    # Phase 2E Home
    care_team_contact: dict | None = None
    last_visit: dict | None = None
    needs_you: list[dict] = Field(default_factory=list)


# Rebuild forward refs for SafetyScoreResponse
SafetyScoreResponse.model_rebuild()
FamilyCareStatusResponse.model_rebuild()
FamilyStaffInboxRowResponse.model_rebuild()
FamilyStaffThreadResponse.model_rebuild()
