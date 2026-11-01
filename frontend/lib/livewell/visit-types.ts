export type VisitCheckin = {
  overall: "normal" | "minor_concern" | "significant_concern" | "emergency";
  mood: "normal" | "low" | "anxious" | "confused";
  mobility: "normal_for_them" | "slight_decline" | "significant_decline" | "fall";
  eating: "normal" | "reduced" | "not_eating";
  medication: "none" | "missed" | "refill" | "change" | "concern";
  new_symptoms: "none" | "yes";
  symptoms_note: string;
  home_safety_issue: "none" | "yes";
  home_safety_note: string;
  new_request: "none" | "yes";
  request_note: string;
  follow_up_required: boolean;
  contact_outcome:
    | "answered_normal"
    | "answered_confused"
    | "answered_distressed"
    | "requested_help"
    | "no_answer";
  mobility_vs_normal: "better" | "same" | "slightly_worse" | "much_worse";
  mood_vs_normal: "better" | "same" | "slightly_worse" | "much_worse";
  eating_vs_normal: "better" | "same" | "slightly_worse" | "much_worse";
  fallen_since_last: "no" | "yes";
  unsteady: "no" | "yes";
  worried_about_falling: "no" | "yes";
  care_manager_note: string;
  family_message: string;
};

export type StabilityMeta = {
  score: number | null;
  center?: number;
  delta_from_baseline?: number | null;
  band?: string;
  label?: string;
  factors?: string[];
};

export type SafeHomeVisit = {
  id: string;
  visit_type: string;
  visited_at: string;
  staff_name: string | null;
  partner_id?: string | null;
  partner_name?: string | null;
  summary: string;
  wellness_notes: string;
  concerns: string[];
  recommendations: string;
  photo_ids: number[];
  photo_urls: string[];
  duration_minutes: number | null;
  status: string;
  experience_rating?: number | null;
  experience_comment?: string | null;
  rated_at?: string | null;
  can_rate?: boolean;
  checkin?: VisitCheckin | null;
  stability_score?: number | null;
  stability?: StabilityMeta | null;
  family_message?: string | null;
  /** Staff responses only. */
  location?: VisitLocation | null;
  staff_feedback?: VisitStaffFeedback | null;
};

/** Where the visit was logged from (the staff device's GPS fix). */
export type VisitLocation = {
  lat: number;
  lng: number;
  accuracy_m?: number;
  captured_at?: string;
  distance_from_home_m?: number;
  home_radius_m?: number;
  at_home?: boolean;
};

/** Care manager's feedback about the visit and household. Never shown to families. */
export type VisitStaffFeedback = {
  rating: number;
  comment: string;
  by_name: string;
  at: string;
};

export const EMPTY_VISIT_CHECKIN: VisitCheckin = {
  overall: "normal",
  mood: "normal",
  mobility: "normal_for_them",
  eating: "normal",
  medication: "none",
  new_symptoms: "none",
  symptoms_note: "",
  home_safety_issue: "none",
  home_safety_note: "",
  new_request: "none",
  request_note: "",
  follow_up_required: false,
  contact_outcome: "answered_normal",
  mobility_vs_normal: "same",
  mood_vs_normal: "same",
  eating_vs_normal: "same",
  fallen_since_last: "no",
  unsteady: "no",
  worried_about_falling: "no",
  care_manager_note: "",
  family_message: "",
};

export type CareBaseline = {
  usual_wake_time: string;
  wake_band?: string;
  typical_mobility: string;
  mobility_band?: string;
  normal_appetite: string;
  appetite_band?: string;
  normal_communication: string;
  communication_band?: string;
  typical_bathroom_frequency: string;
  bathroom_band?: string;
  normal_activity_level: string;
  activity_band?: string;
  usual_sleep_pattern: string;
  sleep_band?: string;
  leaves_home_how_often: string;
  leaves_home_band?: string;
  mobility_limitations: string;
  known_fall_history: string;
  fall_history_band?: string;
  typical_medication_routine: string;
  meds_band?: string;
  home_hazard_band?: string;
  unsteady_at_baseline?: string;
  worried_about_falling_baseline?: string;
  notes: string;
  context_notes?: string;
  home_glance_notes?: string;
  normal_day_confirmed?: string;
  close_notes?: string;
  updated_at?: string | null;
  baseline_stability_score?: number;
};
