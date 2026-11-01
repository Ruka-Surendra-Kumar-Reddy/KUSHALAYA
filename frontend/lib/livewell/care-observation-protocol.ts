/**
 * Caregiver observation protocol — Observe / Ask / Record.
 * Inspired by WHO ICOPE domains + CDC STEADI fall cues (not a certified instrument).
 */

export type ProtocolSource = "icope" | "steadi" | "aarp" | "livewell";

export type ObservationStep = {
  id: string;
  title: string;
  observe: string;
  ask: string[];
  fields: string[];
  source?: ProtocolSource;
  tip?: string;
};

export const PROTOCOL_SOURCES = [
  {
    id: "icope" as const,
    name: "WHO ICOPE",
    note: "Domain map for community care workers (locomotion, vitality, mood/cognition light).",
  },
  {
    id: "steadi" as const,
    name: "CDC STEADI",
    note: "Fall cues: fallen / unsteady / worried; meds and home hazards.",
  },
  {
    id: "aarp" as const,
    name: "AARP HomeFit (framing)",
    note: "Light home glance only — full home scoring stays with KAA assessment.",
  },
];

export const BASELINE_STABILITY_SCORE = 50;

export const MOBILITY_BAND_OPTIONS = [
  { value: "independent", label: "Independent (no aid)" },
  { value: "cane", label: "Cane / stick" },
  { value: "walker", label: "Walker / rollator" },
  { value: "assisted", label: "Needs assistance" },
  { value: "chairbound", label: "Mostly chair / bed" },
] as const;

export const COMMUNICATION_BAND_OPTIONS = [
  { value: "clear", label: "Clear and engaged" },
  { value: "some_difficulty", label: "Some difficulty / hard of hearing" },
  { value: "confused", label: "Confused at times" },
  { value: "hard_to_engage", label: "Hard to engage / withdrawn" },
] as const;

export const APPETITE_BAND_OPTIONS = [
  { value: "good", label: "Good" },
  { value: "fair", label: "Fair" },
  { value: "poor", label: "Poor" },
] as const;

export const LEAVES_HOME_BAND_OPTIONS = [
  { value: "daily", label: "Daily / almost daily" },
  { value: "few_times_week", label: "A few times a week" },
  { value: "rarely", label: "Rarely" },
  { value: "never", label: "Almost never" },
] as const;

export const FALL_HISTORY_BAND_OPTIONS = [
  { value: "none", label: "No falls" },
  { value: "one_past_year", label: "One fall in past year" },
  { value: "multiple", label: "More than one in past year" },
  { value: "recent", label: "Recent fall (with or without injury)" },
] as const;

export const WAKE_BAND_OPTIONS = [
  { value: "before_6", label: "Before 6 AM" },
  { value: "6_to_7", label: "6–7 AM" },
  { value: "7_to_8", label: "7–8 AM" },
  { value: "after_8", label: "After 8 AM" },
  { value: "irregular", label: "Irregular / varies" },
] as const;

export const SLEEP_BAND_OPTIONS = [
  { value: "through_night", label: "Sleeps through the night" },
  { value: "wakes_once", label: "Wakes once (e.g. bathroom)" },
  { value: "restless", label: "Restless / frequent waking" },
  { value: "day_night_reversed", label: "Day–night reversed" },
] as const;

export const ACTIVITY_BAND_OPTIONS = [
  { value: "active_home", label: "Moves freely around the home" },
  { value: "limited", label: "Limited — short walks only" },
  { value: "mostly_seated", label: "Mostly seated" },
  { value: "mostly_bed", label: "Mostly in bed / chairbound" },
] as const;

export const BATHROOM_BAND_OPTIONS = [
  { value: "independent", label: "Independent" },
  { value: "occasional_help", label: "Occasional help" },
  { value: "night_trips", label: "Frequent night trips" },
  { value: "needs_assistance", label: "Needs assistance" },
] as const;

export const MEDS_BAND_OPTIONS = [
  { value: "self", label: "Self-manages" },
  { value: "family", label: "Family manages" },
  { value: "caregiver", label: "Caregiver / nurse manages" },
  { value: "irregular", label: "Irregular / often missed" },
] as const;

export const HOME_HAZARD_BAND_OPTIONS = [
  { value: "none_seen", label: "No obvious hazards on main path" },
  { value: "minor", label: "Minor clutter / lighting issue" },
  { value: "significant", label: "Significant trip/fall hazard" },
  { value: "not_assessed", label: "Not assessed this visit" },
] as const;

export const YES_NO_OPTIONS = [
  { value: "no", label: "No" },
  { value: "yes", label: "Yes" },
] as const;

export const BASELINE_STEPS: ObservationStep[] = [
  {
    id: "arrive",
    title: "Arrive & context",
    observe: "Who opens the door; who else is present; general appearance.",
    ask: ["Confirm name.", "Who’s here with you today?"],
    fields: ["context_notes"],
    source: "livewell",
  },
  {
    id: "alertness",
    title: "Contact / alertness",
    observe: "Eye contact, speech clarity, confusion, or distress.",
    ask: ["How are you feeling today?"],
    fields: ["communication_band", "normal_communication"],
    source: "icope",
    tip: "ICOPE: psychological + light cognition screen — not a full cognitive test.",
  },
  {
    id: "mobility",
    title: "Mobility & falls",
    observe: "Sit-to-stand, short walk (room → hall/kitchen), aids used, unsteadiness.",
    ask: [
      "Have you fallen recently?",
      "Do you feel unsteady when walking?",
      "Are you worried about falling?",
    ],
    fields: [
      "mobility_band",
      "fall_history_band",
      "unsteady_at_baseline",
      "worried_about_falling_baseline",
      "typical_mobility",
      "mobility_limitations",
      "known_fall_history",
    ],
    source: "steadi",
    tip: "STEADI fall cues + ICOPE locomotion. Use the dropdowns; free text for detail only.",
  },
  {
    id: "rhythm",
    title: "Daily rhythm",
    observe: "Energy level; whether they seem housebound vs active.",
    ask: ["What time do you usually wake?", "How is your sleep?", "How often do you leave home?"],
    fields: ["wake_band", "sleep_band", "leaves_home_band", "activity_band"],
    source: "icope",
  },
  {
    id: "eating",
    title: "Eating & bathroom",
    observe: "Meal evidence if visible (plates, fridge use) — light only.",
    ask: ["What is a typical day of meals for you?", "Any usual bathroom pattern we should know?"],
    fields: ["appetite_band", "bathroom_band", "normal_appetite", "typical_bathroom_frequency"],
    source: "icope",
    tip: "ICOPE vitality (nutrition) + light continence on baseline only.",
  },
  {
    id: "meds",
    title: "Medications",
    observe: "Where meds are kept; organizer vs loose bottles.",
    ask: ["Who manages your medicines?", "What is the usual timing?"],
    fields: ["meds_band", "typical_medication_routine"],
    source: "steadi",
  },
  {
    id: "home",
    title: "Home glance",
    observe: "Trip hazards on the main path: clutter, loose rugs, poor lighting.",
    ask: [],
    fields: ["home_hazard_band", "home_glance_notes"],
    source: "aarp",
    tip: "Glance only — full HomeFit / KAA assessment is separate.",
  },
  {
    id: "close",
    title: "Close",
    observe: "Confirm this matches a normal day for them.",
    ask: ["Does this sound like a normal day for you?"],
    fields: ["normal_day_confirmed", "close_notes"],
    source: "livewell",
    tip: `Baseline stability score is anchored at ${BASELINE_STABILITY_SCORE} so later visits can show improvement or decline.`,
  },
];

export const CHECKIN_STEPS: ObservationStep[] = [
  {
    id: "contact",
    title: "Contact",
    observe: "Did they answer? Sound normal, confused, or distressed?",
    ask: [],
    fields: ["contact_outcome"],
    source: "icope",
  },
  {
    id: "mood",
    title: "Mood vs their normal",
    observe: "Affect vs usual (low, anxious, confused).",
    ask: ["How is your mood compared with usual?"],
    fields: ["mood", "mood_vs_normal"],
    source: "icope",
  },
  {
    id: "mobility",
    title: "Mobility & falls vs their normal",
    observe: "Short walk vs their baseline; any unsteadiness.",
    ask: [
      "Have you fallen since the last visit?",
      "Do you feel unsteady?",
      "Are you worried about falling?",
      "Is walking the same as usual for you?",
    ],
    fields: [
      "fallen_since_last",
      "unsteady",
      "worried_about_falling",
      "mobility",
      "mobility_vs_normal",
    ],
    source: "steadi",
  },
  {
    id: "eating",
    title: "Eating vs their normal",
    observe: "—",
    ask: ["Are you eating the same as usual?"],
    fields: ["eating", "eating_vs_normal"],
    source: "icope",
  },
  {
    id: "flags",
    title: "Meds, symptoms, home, requests",
    observe: "New hazard on the main path; distress signals.",
    ask: [
      "Any missed medicines or refill needs?",
      "Any new symptoms?",
      "Anything that needs follow-up?",
    ],
    fields: [
      "medication",
      "new_symptoms",
      "home_safety_issue",
      "new_request",
      "follow_up_required",
    ],
    source: "steadi",
  },
  {
    id: "overall",
    title: "Overall judgment",
    observe: "After steps above — care coordination judgment (not a diagnosis).",
    ask: [],
    fields: ["overall", "family_message"],
    source: "livewell",
    tip: "Write a short message the family will see on their dashboard.",
  },
];
