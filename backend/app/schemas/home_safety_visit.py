from datetime import datetime

from pydantic import BaseModel, Field


class VisitCheckinPayload(BaseModel):
    """Structured 60–90s Care Manager check-in (Mom-is-OK status)."""

    overall: str = "normal"
    mood: str = "normal"
    mobility: str = "normal_for_them"
    eating: str = "normal"
    medication: str = "none"
    new_symptoms: str = "none"
    symptoms_note: str = ""
    home_safety_issue: str = "none"
    home_safety_note: str = ""
    new_request: str = "none"
    request_note: str = ""
    follow_up_required: bool = False
    contact_outcome: str = "answered_normal"
    mobility_vs_normal: str = "same"
    mood_vs_normal: str = "same"
    eating_vs_normal: str = "same"
    fallen_since_last: str = "no"
    unsteady: str = "no"
    worried_about_falling: str = "no"
    care_manager_note: str = ""
    family_message: str = ""


class CareBaselinePayload(BaseModel):
    usual_wake_time: str = ""
    wake_band: str = ""
    typical_mobility: str = ""
    mobility_band: str = ""
    normal_appetite: str = ""
    appetite_band: str = ""
    normal_communication: str = ""
    communication_band: str = ""
    typical_bathroom_frequency: str = ""
    bathroom_band: str = ""
    normal_activity_level: str = ""
    activity_band: str = ""
    usual_sleep_pattern: str = ""
    sleep_band: str = ""
    leaves_home_how_often: str = ""
    leaves_home_band: str = ""
    mobility_limitations: str = ""
    known_fall_history: str = ""
    fall_history_band: str = ""
    typical_medication_routine: str = ""
    meds_band: str = ""
    home_hazard_band: str = ""
    unsteady_at_baseline: str = ""
    worried_about_falling_baseline: str = ""
    notes: str = ""
    context_notes: str = ""
    home_glance_notes: str = ""
    normal_day_confirmed: str = ""
    close_notes: str = ""


class CareBaselineResponse(CareBaselinePayload):
    updated_at: datetime | None = None
    baseline_stability_score: int = 50


class VisitLocationPayload(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy_m: float | None = None
    captured_at: datetime | None = None


class VisitStaffFeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = ""


class VisitPhotoAttachRequest(BaseModel):
    photo_ids: list[int] = Field(default_factory=list)


class SafeHomeVisitCreate(BaseModel):
    elder_id: int
    visit_type: str = "Wellness visit"
    visited_at: datetime | None = None
    staff_name: str = ""
    partner_id: str = ""
    summary: str = ""
    wellness_notes: str = ""
    concerns: list[str] = Field(default_factory=list)
    recommendations: str = ""
    photo_ids: list[int] = Field(default_factory=list)
    duration_minutes: int | None = None
    status: str = "completed"
    checkin: VisitCheckinPayload | None = None
    baseline: CareBaselinePayload | None = None
    family_message: str = ""
    location: VisitLocationPayload | None = None


class SafeHomeVisitResponse(BaseModel):
    id: str
    visit_type: str
    visited_at: datetime
    staff_name: str | None
    partner_id: str | None = None
    partner_name: str | None = None
    summary: str
    wellness_notes: str
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
    stability_score: int | None = None
    stability: dict | None = None
    family_message: str | None = None
    # Staff responses only; always None for families.
    location: dict | None = None
    staff_feedback: dict | None = None


class VisitExperienceRatingRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = ""
