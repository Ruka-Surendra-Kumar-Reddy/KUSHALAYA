/**
 * Caregiver checklist wording: a plain question and what the caregiver sees,
 * instead of asking them to judge "Safe / Needs attention / Risk" (owner, 12 Oct).
 * Each answer still saves the same rating (excellent / acceptable / unsafe / na),
 * so the score is unchanged. Wording follows the level descriptions in
 * assessor-item-training.ts. Questions missing here fall back to the old buttons.
 */
export type CaregiverAnswers = {
  /** The question as asked in the home. */
  ask: string;
  excellent: string;
  acceptable: string;
  unsafe: string;
  /** Real "does not apply" wording. Omitted when every answer is a real rating;
   *  the separate N/A chip still sets "na". */
  na?: string;
};

const A = (ask: string, excellent: string, acceptable: string, unsafe: string, na?: string): CaregiverAnswers => ({
  ask,
  excellent,
  acceptable,
  unsafe,
  ...(na ? { na } : {}),
});

export const CAREGIVER_ANSWERS: Record<string, CaregiverAnswers> = {
  // Home safety
  home_safety_toilet_grab_bar_installed: A("Is there a grab bar by the toilet?", "Yes, fixed firmly and used", "Yes, but badly placed or one side only", "No bar, or it's loose", "They never use this toilet alone"),
  home_safety_shower_grab_bar_installed: A("Is there a grab bar where they bathe?", "Yes, fixed firmly and used", "Yes, but badly placed", "No bar — they hold the wall or pipes", "Always bathed by a caregiver"),
  home_safety_anti_slip_flooring: A("Is the bathroom floor non-slip?", "Anti-slip tiles or a fixed mat", "Loose or partial mat only", "Smooth tiles, wet, no mat", "They never use this bathroom"),
  home_safety_shower_chair_available: A("Do they have a shower chair or stool?", "Yes, a proper shower chair", "A household stool, steady enough", "None, or a wobbly one", "No balance problems, not needed"),
  home_safety_toilet_height_appropriate: A("Can they sit on and get up from the toilet easily?", "Yes, easily", "Needs to hold on or push up", "Too low, or squat toilet — struggles", "Uses a commode or bedpan"),
  home_safety_hot_water_scald_risk_controlled: A("Is hot water safe for them?", "Geyser set to a safe temperature", "No control, but someone checks it", "They handle very hot water alone", "Never handles hot water"),
  home_safety_bathroom_well_ventilated: A("Does the bathroom dry out after bathing?", "Yes, exhaust fan or window works", "Some air, floor stays damp", "No fan or window — stays wet", "They don't use this bathroom"),
  home_safety_pathway_level_and_clear: A("Are the walking paths level and clear?", "Yes, clear and level", "Mostly clear, the odd item", "Wires, footwear or bumps in the way", "They don't walk"),
  home_safety_zero_step_or_ramped_main_entry: A("How is the main entrance?", "No step, or a ramp", "One low step they manage", "High step or several steps", "They never use it alone"),
  home_safety_entrance_railing_if_needed: A("Is there a railing at the entrance steps?", "Yes, firm and they use it", "Yes, but wrong side or height", "Steps but no railing", "No steps at the entrance"),
  home_safety_adequate_entry_lighting: A("Is the entrance lit?", "Yes, bright, switch easy to reach", "Light works, switch hard to reach", "No working light", "Never uses it after dark"),
  home_safety_hallways_free_of_trip_hazards: A("Are the hallways clear?", "Yes, clear", "Some clutter now and then", "Clutter or wires all the time", "No hallway"),
  home_safety_loose_rugs_secured_or_removed: A("Are there loose rugs or mats where they walk?", "None, or all fixed down", "A flat one, out of the way", "Curling or loose mats in their path", "No rugs or mats"),
  home_safety_bedroom_night_lighting: A("Is there a light for getting up at night?", "Night light, or switch near bed", "A torch or lamp within reach", "Dark — no light", "They don't get up at night"),
  home_safety_bed_transfer_support: A("Can they get in and out of bed safely?", "Yes, good height, firm hold nearby", "Manages, sometimes struggles", "Bed too low or soft, nothing to hold", "Always helped by a caregiver"),
  home_safety_smoke_and_co_detectors_on_each_level: A("Is there a working smoke alarm?", "Yes, working, on each floor", "One working, near the kitchen", "None, or not working", "Not relevant here"),
  home_safety_stove_gas_safety_controls: A("Is the gas stove safe to use?", "Good hose, gas turned off after use", "Hose old, due for change", "Cracked hose, or gas left on before", "They never use the stove"),
  home_safety_living_area_walkways_clear: A("Is the living room easy to walk through?", "Yes, clear", "One small thing to walk around", "Furniture or wires block the way", "They don't use this room alone"),

  // Mobility
  mobility_walks_independently_or_with_correct_devi: A("How do they walk?", "Steady, or uses stick/walker well", "A bit unsteady, stick/walker sometimes", "Can't walk, or won't use needed walker"),
  mobility_balance_adequate_for_home: A("How is their balance?", "Good", "Wobbles a little, then steadies", "Holds furniture, or can't stand alone"),
  mobility_stands_from_chair_without_arm_push: A("Can they stand up from a chair?", "Yes, without using hands", "Pushes up with hands", "Needs help or many tries, or can't"),
  mobility_transfers_bed_chair_safely: A("Can they move between bed and chair?", "Yes, safely, or lifted by caregiver", "Slowly, holding something", "Needs a lot of help"),
  mobility_stairs_manageable_or_alternative_exists: A("Can they manage the stairs?", "Yes, safely", "Only with someone there", "Tries alone, unsafe", "No stairs at home"),
  mobility_door_widths_thresholds_accessible: A("Do doors fit their walker or wheelchair?", "Yes, easily", "Tight, but they get through", "Too narrow, or high door step", "No walker or wheelchair"),
  mobility_wheelchair_or_walker_path_clear: A("Is there room for their walker or wheelchair?", "Yes, clear", "Tight in one place", "Blocked — they leave it behind", "No walker or wheelchair"),

  // Health
  health_wellness_chronic_conditions_documented: A("Are their health conditions written down?", "Yes, written and up to date", "Family knows, not written", "Family isn't sure", "No long-term conditions"),
  health_wellness_medications_reconciled: A("Do their medicines match the prescription?", "Yes, list matches", "Mostly, list a bit old", "Doesn't match, or expired medicines", "No regular medicines"),
  health_wellness_meds_checked_for_dizziness_sedation: A("Do any medicines make them dizzy or sleepy?", "Doctor has reviewed them", "Yes, family knows, doctor not asked", "Yes, and no one has checked", "No such medicines"),
  health_wellness_pain_managed_acceptably: A("Are they in pain?", "No, or well controlled", "Some pain, partly controlled", "A lot of pain, not treated"),
  health_wellness_vision_hearing_supports_in_place: A("Do they have the glasses or hearing aid they need?", "Uses them, or sees and hears well", "Has them, old or not always used", "Needs them, doesn't have them"),
  health_wellness_nutrition_adequate: A("Are they eating well?", "Yes, good meals", "Enough, but little variety", "Skips meals or losing weight", "Not relevant"),
  health_wellness_bp_sugar_checked_regularly: A("Are BP and sugar checked at home?", "Yes, regularly", "Now and then", "Needed but not checked", "Not needed"),
  health_wellness_no_falls_in_the_past_year: A("Have they fallen in the last year?", "No falls", "One small slip, no injury", "Yes, has fallen, or bed-bound"),
  health_wellness_steady_when_walking: A("Are they steady when walking?", "Yes, steady", "Sometimes a bit unsteady", "Clearly unsteady, or can't walk"),
  health_wellness_not_worried_about_falling: A("Are they worried about falling?", "No", "A little, still active", "Very — avoids bathing or walking", "Can't tell us"),
  health_wellness_rush_to_toilet_urgency_managed: A("Do they have to rush to the toilet?", "No", "Sometimes, manageable", "Often, toilet far or dark"),
  health_wellness_foot_sensation_adequate_for_walking: A("Can they feel their feet well?", "Yes, no numbness", "A little numb, takes care", "Very numb, unsafe footwear"),

  // Daily living (ADL)
  adl_bathing_independently_or_with_plan: A("How do they bathe?", "Safe alone, or caregiver helps as planned", "With some help", "Bathes alone unsafely, no help"),
  adl_dressing_independently_or_with_plan: A("Can they dress themselves?", "Yes, or caregiver helps as planned", "Needs help with some things", "Can't, and no regular help"),
  adl_toileting_independently_or_with_plan: A("Can they use the toilet on their own?", "Yes, or caregiver helps as planned", "Needs some help or time", "Struggles, no help"),
  adl_eating_feeding_independence: A("Can they eat on their own?", "Yes", "Needs some help", "Can't, or chokes on food", "Not relevant"),
  adl_transfer_mobility_for_adls: A("Can they move around for daily tasks?", "Yes, safely", "With a little help, or stick/walker", "Can't manage, or fully immobile"),
  adl_personal_hygiene_maintained: A("How is their personal hygiene?", "Good", "Mostly fine, some lapses", "Clearly neglected", "Not relevant"),

  // Household tasks (IADL)
  iadl_manages_medications_schedule: A("Do they take medicines on time?", "Yes, reliably", "Sometimes missed or late", "Often missed or doubled", "No regular medicines"),
  iadl_prepares_or_receives_meals_safely: A("How do they get their meals?", "Cooks safely, or meals arranged", "Meals happen, with some gaps", "Unsafe cooking or missed meals", "Not relevant"),
  iadl_handles_shopping_errands: A("Are shopping and errands taken care of?", "Yes, someone reliable does it", "Help only now and then", "No one — things run out", "Not relevant"),
  iadl_manages_finances_or_has_help: A("Is their money managed well?", "They do, or family helps well", "Mostly fine, some lapses", "Problems, or no one helps", "Not relevant"),
  iadl_uses_transportation_safely: A("How do they travel outside?", "Safely, transport arranged", "Manages, depends on others", "Unsafe, or never goes out"),
  iadl_light_housework_manageable: A("Is the housework getting done?", "Yes, home kept well", "Done only sometimes", "Stopped — home neglected", "Not relevant"),

  // Memory and mood
  cognitive_emotional_orientation_to_person_place_time: A("Do they know the place, people and day?", "Yes, clearly", "Unsure of the date only", "Very confused", "Not relevant"),
  cognitive_emotional_mood_stable_no_untreated_depression: A("How is their mood?", "Good, steady", "Sometimes low", "Very low or withdrawn", "Not relevant"),
  cognitive_emotional_memory_adequate_for_daily_safety: A("Is their memory safe for daily life?", "Yes", "Forgets things, someone helps", "Forgetting has caused near-misses", "Not relevant"),
  cognitive_emotional_judgment_safe_for_leaving_stove_doors: A("Do they leave the stove on or doors open?", "No", "Rarely, family checks", "Yes, it has happened", "No access to stove or doors"),
  cognitive_emotional_social_engagement_present: A("Do they meet or talk to people?", "Yes, regularly", "Sometimes", "Hardly ever — isolated", "Not relevant"),
  cognitive_emotional_safe_from_wandering_getting_lost: A("Have they wandered off or got lost?", "No, never", "Once, or confused at times", "Yes, and no door alarm", "Can't leave the home"),

  // Emergency
  emergency_emergency_contacts_posted: A("Are emergency numbers on display?", "Yes, put up where easy to see", "Saved in a phone only", "Nowhere they can find", "Not relevant"),
  emergency_sos_alert_method_available: A("Can they call for help if alone?", "Yes, SOS band or phone always on them", "Phone, but not always near", "No way to call for help", "Never alone"),
  emergency_evacuation_path_understood: A("Do they know how to get out in an emergency?", "Yes, knows a clear way out", "Way out exists, not practised", "No plan, or way out blocked", "Not relevant"),
  emergency_first_aid_flashlight_accessible: A("Is there a first-aid kit and a torch?", "Both, easy to find", "Only one of them", "Neither", "Not relevant"),
  emergency_family_response_plan_documented: A("Does the family have an emergency plan?", "Yes, written down", "Known, not written", "No plan", "Not relevant"),

  // Home condition
  home_condition_no_major_structural_hazards: A("Any cracks or damage in walls or roof?", "No", "Small cracks only", "Big cracks or unstable parts", "Not relevant"),
  home_condition_electrical_outlets_wiring_safe: A("Is the electrical wiring safe?", "Yes", "Overloaded plug board or loose socket", "Exposed wires or burn marks", "Not relevant"),
  home_condition_damp_mold_controlled: A("Any damp or fungus (mould) on walls?", "No", "Small damp patches", "Mould or wet walls", "Not relevant"),
  home_condition_plumbing_reliable: A("Are water supply and plumbing reliable?", "Yes", "Small issues", "Leaks or water problems", "Not relevant"),
  home_condition_repairs_backlog_acceptable: A("Are any repairs pending?", "None important", "Some, nothing unsafe", "Safety repairs left undone", "Not relevant"),

  // Technology
  technology_can_use_phone_for_emergencies: A("Can they use a phone to call for help?", "Yes", "With some help", "No", "Always with a caregiver"),
  technology_video_call_capable_self_or_family: A("Can they do video calls?", "Yes, or someone there helps", "Needs help each time", "No one can set it up", "Family lives nearby"),
  technology_smart_safety_devices_appropriate: A("Do they have safety devices (SOS, sensors)?", "Yes, the right ones, and used", "Some, not used much", "None, though needed", "Has a 24/7 caregiver"),
  technology_medication_reminder_tech_if_needed: A("Is there a medicine reminder?", "Works, or manages on their own", "Family reminds, sometimes missed", "None, though needed"),
  technology_wi_fi_power_backup_considered: A("Is there power backup (inverter) and Wi-Fi?", "Yes, both", "Backup for short cuts only", "No backup, frequent cuts", "Stable power, not needed"),
  technology_light_switches_easy_to_reach_and_operate: A("Can they reach the light switches easily?", "Yes, all", "Most, a few hard to reach", "Walks in the dark to a switch", "A caregiver always does it"),
  technology_home_secure_locks_visitor_check: A("Is the home secure?", "Good locks, can check visitors", "Good locks, no visitor check", "Weak locks or door left open", "Never alone at home"),

  // Family support (ask the family)
  family_support_primary_caregiver_family_identified: A("Who is the main family caregiver?", "One clearly named person", "Someone helps, not fixed", "No one clear", "Not relevant"),
  family_support_check_in_frequency_adequate: A("How often does family check on them?", "Often enough", "A bit less than needed", "Rarely", "Has a 24/7 caregiver"),
  family_support_nri_remote_family_plan_if_applicable: A("If family is far away, is there a local plan?", "Yes, someone local responds", "In touch, no local responder", "No one local to respond", "Family is local"),
  family_support_caregiver_stress_manageable: A("How is the family caregiver coping?", "Well", "Some strain, coping", "Exhausted or burnt out", "Paid caregivers only"),
  family_support_advance_directive_decision_maker_known: A("Who decides for them if they can't?", "A person named and agreed", "Understood, not written", "No one agreed", "Not needed now"),
  family_support_willing_to_engage_ecm_if_recommended: A("Is the family open to a care manager?", "Yes", "Unsure", "No", "Not needed"),

  // Money and benefits (ask the family)
  financial_benefits_income_pension_status_known: A("Is their income or pension enough?", "Yes, known and enough", "Just enough, tight", "Unclear or not enough", "Not relevant"),
  financial_benefits_health_insurance_schemes_reviewed: A("Do they have health insurance?", "Yes, policy checked", "Yes, policy not checked", "No cover"),
  financial_benefits_eligible_government_benefits_identified: A("Do they get government benefits?", "Yes, all they're eligible for", "Some", "None explored", "Not eligible"),
  financial_benefits_documents_available_for_applications: A("Are key documents (Aadhaar, pension) at hand?", "Yes, all", "Most, but scattered", "Missing", "None needed"),
  financial_benefits_budget_for_home_improvements_realistic: A("Can the family pay for safety fixes?", "Yes, budget ready", "Willing, budget unsure", "No budget", "No fixes needed"),

  // Daily life
  lifestyle_day_structure_routine_present: A("Do they have a daily routine?", "Yes, a good routine", "Loose routine", "No routine, days feel empty", "Not relevant"),
  lifestyle_social_contacts_weekly: A("Do they see people outside the home each week?", "Yes, several", "One or two", "Hardly anyone", "Not relevant"),
  lifestyle_meaningful_activities_available: A("Do they have things they enjoy doing?", "Yes", "A few things", "Nothing — bored", "Not relevant"),
  lifestyle_outdoor_community_access: A("Do they get outside or to the temple, park, market?", "Yes, often", "Less than they'd like", "Stuck indoors", "Prefers staying in"),
  lifestyle_sleep_environment_supportive: A("Is their bedroom good for sleep?", "Yes", "Small issue (noise, heat)", "Poor — they sleep badly", "Not relevant"),
};

/** Wording for one question, or null to keep the generic buttons. */
export function caregiverAnswers(id: string): CaregiverAnswers | null {
  return CAREGIVER_ANSWERS[id] ?? null;
}
