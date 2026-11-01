/**
 * Assessor training content for every LiveWell360 Assessment (KAA) checklist item.
 *
 * This is the authoritative "how do I actually rate this?" reference for assessors —
 * what to look for, and what separates Excellent / Acceptable / Unsafe / N/A for each
 * of the ~83 KAA items. Written for Hyderabad / Indian home contexts where relevant,
 * and dignity-first in tone (we describe risk and support needs, not judgment of the elder).
 *
 * ids/labels/categoryIds are kept in exact sync with `lwa-rubric.ts` so this can be
 * looked up by item id or by label.
 *
 * @see lwa-rubric.ts for the scored checklist this trains assessors on.
 */

export type AssessorItemTraining = {
  id: string;
  label: string;
  categoryId: string;
  /** What to observe / ask */
  lookFor: string;
  excellent: string;
  acceptable: string;
  unsafe: string;
  /** When to use N/A */
  naWhen: string;
  tip?: string;
};

export const ASSESSOR_ITEM_TRAINING: AssessorItemTraining[] = [
  // ── 1. Home Safety ──────────────────────────────────────────────────────
  {
    id: "home_safety_toilet_grab_bar_installed",
    label: "Toilet grab bar installed",
    categoryId: "home_safety",
    lookFor:
      "Look for a securely mounted grab bar beside the Indian-style or Western toilet, at a height and angle the elder can actually reach when seated. Ask them to demonstrate using it.",
    excellent:
      "Grab bar (or two, at seat and wall) is professionally mounted into a stud/masonry anchor, at correct height, and the elder uses it confidently every time.",
    acceptable:
      "A grab bar exists but is slightly mispositioned or single-sided, or the elder only uses it sometimes — it still provides real support.",
    unsafe:
      "No grab bar, or one that is loose, mounted into hollow tile/putty only, or the elder instead grips a towel rod, geyser pipe, or wall ledge for support.",
    naWhen:
      "Elder never uses this toilet unassisted (always transferred by a caregiver), or the home has no attached toilet in regular use.",
    tip: "In many Hyderabad flats a rusted or wobbly towel rod is mistaken for a grab bar — test it by pulling, don't just look.",
  },
  {
    id: "home_safety_shower_grab_bar_installed",
    label: "Shower grab bar installed",
    categoryId: "home_safety",
    lookFor:
      "Check the bathing area (shower stall or bucket-bath corner) for a grab bar reachable from a standing or seated bathing position.",
    excellent:
      "Grab bar solidly anchored at the shower/bathing area, positioned for both standing and sit-to-stand support, used consistently.",
    acceptable:
      "Bar present but not ideally placed, or the elder relies on it only occasionally since most bathing is seated with a bucket and mug.",
    unsafe:
      "No grab bar in the wet area; elder braces on a wet wall, geyser, bucket stand, or a family member's arm every time.",
    naWhen: "Elder is fully bathed by a caregiver and never stands unsupported in the bathing area.",
    tip: "Many Indian bathrooms combine toilet and bathing space in one small room — check that a single bar isn't expected to cover both zones.",
  },
  {
    id: "home_safety_anti_slip_flooring",
    label: "Anti-slip flooring",
    categoryId: "home_safety",
    lookFor:
      "Check the bathroom/wet-area floor finish (tile type, mats) and how it behaves wet — walk it yourself if safe, or ask about past slips.",
    excellent:
      "Anti-slip tile, textured finish, or a well-secured rubber-backed mat covers the entire wet zone; the floor is never left standing with water.",
    acceptable:
      "Smooth tile with a loose or partial mat that reduces but doesn't eliminate slip risk; the household is aware and careful.",
    unsafe:
      "Glazed/polished tile with standing water and no mat, or a mat that itself slides — a classic bathroom fall hazard.",
    naWhen: "Mark N/A only if the elder never enters this wet area at all.",
    tip: "Ask the family directly: \u201cHas anyone slipped here before?\u201d — most report at least a near-miss on wet glazed tile.",
  },
  {
    id: "home_safety_shower_chair_available",
    label: "Shower chair available",
    categoryId: "home_safety",
    lookFor:
      "Ask if bathing is done standing, seated on a plastic stool, or with a proper shower/commode chair; check its stability.",
    excellent:
      "A stable, non-slip plastic or purpose-built shower chair with a wide base and no wobble is used every bath.",
    acceptable: "A household plastic stool is used and is reasonably stable, even if not purpose-built for bathing.",
    unsafe: "Elder bathes standing despite balance issues, or uses a cracked/wobbly stool that could tip.",
    naWhen:
      "Elder has no balance or standing concerns and safely bathes standing, or is fully assisted lying down/in bed.",
  },
  {
    id: "home_safety_toilet_height_appropriate",
    label: "Toilet height appropriate",
    categoryId: "home_safety",
    lookFor: "Check seat height relative to the elder's knee height; watch them sit down and stand up.",
    excellent:
      "Western-style toilet at a comfortable height (or a raised seat/commode fitted); elder sits/stands without strain.",
    acceptable:
      "Height is workable but the elder needs to hold something or push off furniture; a raised seat has been discussed but not yet fitted.",
    unsafe:
      "Very low seat (or an Indian-style squat toilet) that forces a deep squat the elder cannot safely perform, with no commode alternative.",
    naWhen: "Elder is fully assisted onto a commode/bedpan and toilet seat height doesn't apply to their use.",
    tip: "Squat (Indian-style) toilets are common in older Hyderabad homes — this is one of the most frequently recommended upgrades (raised commode or Western conversion).",
  },
  {
    id: "home_safety_hot_water_scald_risk_controlled",
    label: "Hot water scald risk controlled",
    categoryId: "home_safety",
    lookFor:
      "Ask how hot water is delivered (geyser, immersion rod, bucket mixed by hand) and whether temperature is checked before bathing.",
    excellent:
      "Geyser/thermostat set to a safe max temperature, or water is always mixed and tested by a caregiver before the elder touches it.",
    acceptable:
      "No thermostat control, but someone reliably tests water temperature by hand each time before bathing.",
    unsafe:
      "Elder (especially if confused) handles boiling water or an immersion rod alone, or hot and cold buckets are left unmarked and easy to confuse.",
    naWhen: "Elder never handles hot water directly and a caregiver fully manages bathing water temperature.",
  },
  {
    id: "home_safety_bathroom_well_ventilated",
    label: "Bathroom well ventilated",
    categoryId: "home_safety",
    lookFor:
      "Run the shower or check after a bath: is there an exhaust fan or opening window? Look for damp walls, mould, condensation on the floor and a musty smell.",
    excellent:
      "Working exhaust fan or window that clears steam quickly; floor and walls dry within minutes, no mould.",
    acceptable:
      "Some ventilation (small window, weak fan) but steam lingers and the floor stays damp for a while.",
    unsafe:
      "No fan or window that opens; floor stays wet and slippery after bathing, or visible mould and damp.",
    naWhen: "Bathroom is not used by the elder.",
  },
  {
    id: "home_safety_pathway_level_and_clear",
    label: "Pathway level and clear",
    categoryId: "home_safety",
    lookFor:
      "Walk the main route the elder uses daily (bedroom to bathroom to kitchen) checking for level flooring and clutter.",
    excellent: "Main paths are flat, well-lit, and free of clutter, cables, footwear, or furniture in the walking line.",
    acceptable:
      "Mostly clear with an occasional movable obstacle (a stool, slippers) that the household is willing to fix.",
    unsafe:
      "Wires, footwear piles near the door, uneven floor transitions, or furniture narrow the path where the elder walks daily.",
    naWhen:
      "Elder is fully non-ambulatory (bed/wheelchair-bound with full-time transfer assistance) and never walks this path independently.",
  },
  {
    id: "home_safety_zero_step_or_ramped_main_entry",
    label: "Zero-step or ramped main entry",
    categoryId: "home_safety",
    lookFor: "Check the main entrance for a threshold step, its height, and whether a ramp exists or is feasible.",
    excellent:
      "Flush or ramped entry (permanent or portable ramp) that the elder or their walker/wheelchair crosses without lifting effort.",
    acceptable:
      "A single low step (under ~4 inches) that the elder manages independently and safely, though a ramp isn't yet installed.",
    unsafe:
      "A high threshold, multiple steps, or a step with no rail that risks a trip or fall on the elder's most-used entry.",
    naWhen:
      "Elder never uses the main entry independently (always assisted), or the home already has a verified step-free entry.",
    tip: "Many Hyderabad independent houses have a raised plinth at the main door — a low-cost wooden or concrete mini-ramp is often the easiest fix.",
  },
  {
    id: "home_safety_entrance_railing_if_needed",
    label: "Entrance railing if needed",
    categoryId: "home_safety",
    lookFor: "If there are entry steps, check for a handrail at a usable height on at least one side.",
    excellent: "Sturdy rail on the step/ramp, correct height, used confidently by the elder.",
    acceptable: "A rail exists but is on the wrong side, slightly high/low, or the elder only sometimes uses it.",
    unsafe: "Steps at the entry with no rail at all, and the elder holds the wall, a plant pot, or a family member instead.",
    naWhen: "Entry is zero-step/flat, so no railing is needed.",
  },
  {
    id: "home_safety_adequate_entry_lighting",
    label: "Adequate entry lighting",
    categoryId: "home_safety",
    lookFor: "Check lighting at the main door in the evening/night — fixture presence, bulb function, switch location.",
    excellent:
      "Bright, working light at the entry, switch reachable before stepping outside, ideally with a dusk sensor or easy-reach switch.",
    acceptable:
      "Light exists and works but the switch is awkwardly placed (e.g., only inside, requiring the elder to step out in the dark first).",
    unsafe: "No functioning light at the entrance, or the elder must navigate steps/threshold in the dark.",
    naWhen: "Elder never uses this entrance after dark or unaccompanied.",
  },
  {
    id: "home_safety_hallways_free_of_trip_hazards",
    label: "Hallways free of trip hazards",
    categoryId: "home_safety",
    lookFor:
      "Walk all hallways/corridors the elder uses, checking for cables, footwear, furniture edges, or storage encroaching on the path.",
    excellent: "Hallways are consistently kept clear, wide enough for the elder's gait or mobility aid, and well lit.",
    acceptable:
      "Generally clear with occasional temporary clutter (drying clothes, a delivery box) the family agrees to manage.",
    unsafe:
      "Persistent clutter, exposed extension cords, or narrow pinch points force the elder to detour or brush against obstacles.",
    naWhen: "No hallway exists between the elder's key rooms (single-room layout).",
  },
  {
    id: "home_safety_loose_rugs_secured_or_removed",
    label: "Loose rugs secured or removed",
    categoryId: "home_safety",
    lookFor: "Check all mats/rugs (including bathroom mats, prayer-room mats, doormats) for slip risk and curling edges.",
    excellent:
      "No loose rugs on the elder's path, or all mats are anti-slip-backed and taped/tacked down flat.",
    acceptable:
      "A rug or two remains but is low-pile, flat, and in a low-traffic area with minimal risk.",
    unsafe: "Curling, unsecured rugs or mats sit directly in the elder's daily walking path.",
    naWhen: "Home has no rugs or mats anywhere the elder walks.",
    tip: "Cotton dari/carpet runners in the living room and prayer-space mats are frequently missed — check beyond just the bathroom mat.",
  },
  {
    id: "home_safety_bedroom_night_lighting",
    label: "Bedroom night lighting",
    categoryId: "home_safety",
    lookFor:
      "Ask about the route from bed to bathroom at night; check for a night light, switch location, or torch within reach.",
    excellent:
      "A dim night light or motion-sensor light illuminates the bed-to-bathroom path; the switch/light is within arm's reach of the bed.",
    acceptable: "No dedicated night light, but a lamp/torch is kept within reach and reliably used.",
    unsafe:
      "Elder navigates a dark room and hallway at night with no light source in reach, risking a fall on the way to the toilet.",
    naWhen:
      "Elder does not get up at night (e.g., uses a bedside commode with a caregiver present) or sleeps in a fully monitored setting.",
  },
  {
    id: "home_safety_bed_transfer_support",
    label: "Bed transfer support",
    categoryId: "home_safety",
    lookFor:
      "Check bed height relative to the elder's knees, mattress firmness, and whether a bed rail, cot side-bar, or sturdy furniture is nearby to push off.",
    excellent:
      "Bed height and firmness suit the elder, plus a bed rail or firmly fixed nearby support for sitting up and standing.",
    acceptable:
      "Bed transfer is manageable but the elder occasionally struggles with a soft/low bed or has to grab an unstable side table.",
    unsafe:
      "Very low or very soft bed height forces unsafe effort, and there is nothing sturdy nearby to hold while getting up.",
    naWhen: "Elder is fully assisted for all bed transfers by a caregiver at all times.",
  },
  {
    id: "home_safety_smoke_and_co_detectors_on_each_level",
    label: "Smoke and CO detectors on each level",
    categoryId: "home_safety",
    lookFor:
      "Check for installed smoke detectors and, if there's a gas geyser or generator indoors, CO detection; test if possible.",
    excellent:
      "Working smoke detector(s) covering the home, tested recently, plus CO detection if gas appliances are present indoors.",
    acceptable: "At least one working smoke detector exists near the kitchen, even if coverage isn't complete across every level.",
    unsafe:
      "No smoke detector anywhere, or one present but with a dead/expired battery, in a home with a gas stove, geyser, or generator.",
    naWhen:
      "Rarely applicable — only if the household already has a monitored fire-alarm system verified independently.",
    tip: "Standalone smoke detectors are uncommon in Hyderabad homes — this is often flagged as a straightforward, low-cost improvement.",
  },
  {
    id: "home_safety_stove_gas_safety_controls",
    label: "Stove / gas safety controls",
    categoryId: "home_safety",
    lookFor:
      "Check the LPG cylinder connection, hose condition, regulator, and whether the elder can safely operate or shut off the stove.",
    excellent:
      "Hose and regulator are in good condition (regularly inspected), the cylinder is secured upright, and either the elder doesn't cook unsupervised where risk is high, or does so safely with reliable shut-off habits.",
    acceptable:
      "Setup is generally safe but the hose is due for replacement, or there is mild forgetfulness about turning off burners that's usually caught by family.",
    unsafe:
      "Worn/cracked gas hose, no reliable shut-off habit, or the elder has previously left a burner on unattended (especially with any memory concerns).",
    naWhen: "Elder never approaches the stove/kitchen (all cooking done by others) and cannot access the gas connection.",
  },
  {
    id: "home_safety_living_area_walkways_clear",
    label: "Living area walkways clear",
    categoryId: "home_safety",
    lookFor:
      "Check the living/sitting room for furniture placement, low tables, wires, and floor clutter along the elder's typical path.",
    excellent:
      "Furniture is arranged with wide, clear walkways; no low coffee tables or cables cross the elder's usual route.",
    acceptable: "Mostly clear, with a minor obstacle (a low stool, a plant) that's avoidable with awareness.",
    unsafe: "Low furniture, wires, or clutter directly block or narrow the elder's path through the main living area.",
    naWhen: "Elder doesn't use this room independently.",
  },

  // ── 2. Mobility & Accessibility ─────────────────────────────────────────
  {
    id: "mobility_walks_independently_or_with_correct_devi",
    label: "Walks independently or with correct device",
    categoryId: "mobility",
    lookFor:
      "Watch the elder walk a short distance in the home; note whether a cane/walker is prescribed and whether it's actually used correctly.",
    excellent: "Walks steadily unaided, or uses the correct device (cane/walker) consistently and with proper technique.",
    acceptable:
      "Walks with mild unsteadiness, or a device is available but used inconsistently without major incident.",
    unsafe:
      "A needed device is refused, missing, the wrong type (e.g., a cane when a walker is needed), or used incorrectly.",
    naWhen: "Elder does not walk at all (fully wheelchair- or bed-bound).",
  },
  {
    id: "mobility_balance_adequate_for_home",
    label: "Balance adequate for home",
    categoryId: "mobility",
    lookFor: "Observe turning, reaching for objects, and short unsupported stances; ask about near-falls or wobbling.",
    excellent: "Steady through turns, reaches, and brief unsupported standing; no reported wobbling.",
    acceptable: "Occasional wobble or wide stance to compensate, but recovers without falling and avoids risky movements.",
    unsafe:
      "Visible unsteadiness, holds onto furniture out of necessity, or reports frequent near-falls during normal movement.",
    naWhen: "Elder does not stand or move independently at all.",
  },
  {
    id: "mobility_stands_from_chair_without_arm_push",
    label: "Stands from chair without arm push",
    categoryId: "mobility",
    lookFor:
      "Ask the elder to stand from a normal chair (not a recliner) without using their hands; watch effort and technique.",
    excellent: "Stands smoothly in one attempt without pushing on armrests or rocking excessively.",
    acceptable: "Needs to push off with hands/armrests but succeeds in one or two attempts without distress.",
    unsafe: "Cannot rise without significant help, multiple attempts, or momentum-rocking that risks a fall.",
    naWhen: "Elder cannot sit in or rise from a standard chair at all due to condition (fully bed-bound).",
    tip: "This is the classic '30-second chair stand' style check used in fall-risk screening — a good proxy for lower-body strength.",
  },
  {
    id: "mobility_transfers_bed_chair_safely",
    label: "Transfers bed/chair safely",
    categoryId: "mobility",
    lookFor:
      "Specifically watch the mechanics of moving from lying to sitting on the bed, and from sitting to standing at a chair — not the full ADL routine.",
    excellent:
      "Smooth, controlled bed-to-sit and chair sit-to-stand transfers with correct hand placement and no loss of balance.",
    acceptable: "Transfers succeed but slowly, with light support from a rail/furniture or one verbal cue.",
    unsafe: "Transfers require significant physical assistance, cause visible strain, or nearly result in a fall.",
    naWhen: "Elder is fully hoisted/lifted by a caregiver for all transfers (no self-initiated movement).",
    tip: "Keep this narrower than \u201cTransfer / mobility for ADLs\u201d — score only the bed and chair mechanics here, not the whole bathing/dressing journey.",
  },
  {
    id: "mobility_stairs_manageable_or_alternative_exists",
    label: "Stairs manageable or alternative exists",
    categoryId: "mobility",
    lookFor:
      "If stairs exist, watch the elder go up/down (or ask about it) and check for a rail; if unused, confirm a workable ground-floor alternative.",
    excellent:
      "Elder manages stairs safely with a rail and good pace, or lives fully on one level with no need for stairs.",
    acceptable:
      "Stairs are manageable only with supervision/assistance, or the elder avoids the upper floor but has a workable ground-floor routine.",
    unsafe: "Elder attempts stairs unsafely alone (no rail, unsteady) with no ground-floor alternative arranged.",
    naWhen: "Home has no stairs at all in the elder's living area.",
  },
  {
    id: "mobility_door_widths_thresholds_accessible",
    label: "Door widths / thresholds accessible",
    categoryId: "mobility",
    lookFor:
      "If the elder uses a walker or wheelchair, observe whether doorways and thresholds allow passage without lifting or scraping.",
    excellent: "All frequently used doorways and thresholds comfortably fit the mobility device with no maneuvering required.",
    acceptable:
      "Passage is possible but tight, requiring the elder to angle the device or get brief help at one doorway.",
    unsafe: "A doorway or threshold is too narrow/high, forcing the elder to abandon the device, be lifted, or risk a fall.",
    naWhen: "Elder does not use a walker or wheelchair.",
  },
  {
    id: "mobility_wheelchair_or_walker_path_clear",
    label: "Wheelchair or walker path clear",
    categoryId: "mobility",
    lookFor: "Trace the elder's actual device path through the home, checking width, turning space, and obstacles.",
    excellent: "Paths are wide and clear enough for the device, with room to turn at corners and doorways.",
    acceptable: "Path is workable but tight in one spot, requiring careful maneuvering rather than a stop.",
    unsafe: "Furniture, rugs, or narrow turns force the elder to fold/abandon the device or squeeze through unsafely.",
    naWhen: "Elder does not use a walker or wheelchair.",
  },

  // ── 3. Health & Wellness ────────────────────────────────────────────────
  {
    id: "health_wellness_chronic_conditions_documented",
    label: "Chronic conditions documented",
    categoryId: "health_wellness",
    lookFor:
      "Ask for a written list of diagnoses (diabetes, hypertension, cardiac, arthritis, etc.) and whether it's kept accessible for emergencies.",
    excellent:
      "Clear, current written record of all chronic conditions, accessible to family and available to show a doctor or paramedic quickly.",
    acceptable: "Conditions are known to the family verbally but not written down anywhere accessible.",
    unsafe:
      "Family/caregiver cannot clearly state the elder's known conditions, or conflicting information is given.",
    naWhen: "Elder has no diagnosed chronic conditions.",
  },
  {
    id: "health_wellness_medications_reconciled",
    label: "Medications reconciled",
    categoryId: "health_wellness",
    lookFor:
      "Review the actual medicine strips/bottles against any prescription list or app; check for duplicates, expired items, or unlabeled pills.",
    excellent:
      "Current medication list matches what's actually in the home, organized (e.g., a pill organizer), with no expired or duplicate drugs.",
    acceptable:
      "Medications are broadly correct but the list is slightly outdated, or organization is informal (loose strips in a drawer).",
    unsafe:
      "Mismatch between prescribed and actual medications, expired drugs still in use, or no one can confirm what's currently being taken.",
    naWhen: "Elder takes no regular medications.",
    tip: "Ask to physically see the strips/bottles rather than relying on a verbal list — discrepancies are common, especially with multiple doctors.",
  },
  {
    id: "health_wellness_meds_checked_for_dizziness_sedation",
    label: "Meds checked for dizziness/sedation",
    categoryId: "health_wellness",
    lookFor:
      "Check whether a doctor or pharmacist has reviewed the medication list specifically for fall-risk side effects (sedatives, BP drugs, sleep aids).",
    excellent:
      "A doctor/pharmacist has reviewed all medications for dizziness/sedation risk and adjusted where needed; no reported daytime grogginess.",
    acceptable:
      "No formal review yet, but the family is aware of which medicines cause drowsiness and times doses/activity around it.",
    unsafe:
      "Elder takes sedating medication (e.g., sleeping pills, certain BP or antihistamine drugs) with no awareness of fall-risk timing, and reports dizziness.",
    naWhen: "Elder takes no medications with known dizziness/sedation risk.",
  },
  {
    id: "health_wellness_pain_managed_acceptably",
    label: "Pain managed acceptably",
    categoryId: "health_wellness",
    lookFor: "Ask directly about pain (joints, back, feet) frequency and intensity, and what's being done about it.",
    excellent: "Pain is well controlled through treatment/management; the elder reports minimal interference with daily activity.",
    acceptable: "Some ongoing pain, partially managed, that limits but doesn't prevent daily function.",
    unsafe: "Significant unmanaged pain that restricts movement or has not been evaluated by a doctor.",
    naWhen: "Elder reports no chronic pain.",
  },
  {
    id: "health_wellness_vision_hearing_supports_in_place",
    label: "Vision/hearing supports in place",
    categoryId: "health_wellness",
    lookFor:
      "Ask about the last eye/hearing check-up; check if glasses/hearing aids are worn, the prescription is current, and the device is in good condition.",
    excellent: "Recent eye and hearing checks done; correct-prescription glasses and/or a working hearing aid used consistently.",
    acceptable:
      "Supports exist but are outdated (old prescription) or used inconsistently; no major daily impact yet.",
    unsafe:
      "Clear vision or hearing decline with no glasses/hearing aid, or a broken/missing device the elder actually needs.",
    naWhen: "No vision or hearing impairment identified.",
  },
  {
    id: "health_wellness_nutrition_adequate",
    label: "Nutrition adequate",
    categoryId: "health_wellness",
    lookFor:
      "Ask about typical daily meals, appetite, weight trend, and who prepares food; note any recent unintentional weight loss.",
    excellent: "Regular, balanced meals appropriate to any dietary restrictions (diabetic, low-salt), stable weight, good appetite.",
    acceptable: "Meals are adequate but repetitive or slightly imbalanced; appetite is fair with no significant weight change.",
    unsafe: "Skipped meals, poor appetite, unexplained weight loss, or inability to prepare/access food without help.",
    naWhen:
      "Rarely applicable — mark N/A only if nutrition is under direct, verified medical/dietitian supervision (e.g., tube feeding) outside this assessment's scope.",
  },
  {
    id: "health_wellness_bp_sugar_checked_regularly",
    label: "BP / sugar checked regularly",
    categoryId: "health_wellness",
    lookFor:
      "Ask how often blood pressure and blood sugar are checked and by whom; look for a working BP monitor or glucometer and a written log for conditions that need it.",
    excellent:
      "Checked as the doctor advised with a working home device (BP monitor / glucometer) and readings written down or shared with family.",
    acceptable:
      "Checked now and then (only at clinic visits, or device present but rarely used / no log).",
    unsafe:
      "Has BP, diabetes or a similar condition that needs home checks, but there is no device and no regular checks.",
    naWhen: "No condition that needs home BP or sugar checks, and the doctor has not asked for them.",
  },
  {
    id: "health_wellness_no_falls_in_the_past_year",
    label: "No falls in the past year",
    categoryId: "health_wellness",
    lookFor:
      "Ask directly and specifically: any fall, slip, or near-fall in the last 12 months, including ones not reported to a doctor.",
    excellent: "No falls or near-falls reported in the past year.",
    acceptable: "One minor slip/stumble with no injury, an isolated incident, no pattern.",
    unsafe: "One or more falls, especially with injury, or a recurring pattern of falls/near-falls.",
    naWhen:
      "Not applicable if the elder has been fully bed-bound/non-ambulatory for the entire past year (no fall exposure).",
    tip: "Families often underreport falls that 'didn't need a doctor' — ask about slips, stumbles, and near-misses too, not just falls requiring treatment.",
  },
  {
    id: "health_wellness_steady_when_walking",
    label: "Steady when walking",
    categoryId: "health_wellness",
    lookFor: "Watch gait during the visit, or ask the elder directly if they feel unsteady when walking (STEADI-style question).",
    excellent: "Gait appears steady on observation, and the elder reports feeling confident/stable while walking.",
    acceptable: "Mild unsteadiness noted occasionally, or the elder reports feeling 'a little' unsteady at times, without falls.",
    unsafe: "Visibly unsteady gait, or the elder reports frequently feeling unsteady/off-balance while walking.",
    naWhen: "Elder does not walk at all.",
  },
  {
    id: "health_wellness_not_worried_about_falling",
    label: "Not worried about falling",
    categoryId: "health_wellness",
    lookFor:
      "Ask directly: 'Are you worried about falling?' Note if fear is limiting activities (avoiding going outside, bathing alone, etc.).",
    excellent: "Elder reports no significant fear of falling and continues normal activities confidently.",
    acceptable: "Some worry exists but the elder still participates in most daily activities without major avoidance.",
    unsafe:
      "Strong fear of falling that has caused the elder to avoid bathing alone, walking outside, or other important activities.",
    naWhen: "Elder is unable to communicate this due to cognitive impairment and no reliable proxy report is available.",
  },
  {
    id: "health_wellness_rush_to_toilet_urgency_managed",
    label: "Rush to toilet / urgency managed",
    categoryId: "health_wellness",
    lookFor: "Ask about urinary/bowel urgency, especially at night, and how quickly the elder must reach the toilet.",
    excellent:
      "No significant urgency, or urgency is well managed with a nearby toilet, night light, and/or a clinical continence plan.",
    acceptable: "Some urgency exists but is manageable with the current toilet distance/routine, without falls resulting.",
    unsafe:
      "Frequent urgent rushing to a distant or poorly lit toilet, especially at night — a known major fall trigger.",
    naWhen: "Elder reports no urgency issues and toilet access is not time-pressured.",
  },
  {
    id: "health_wellness_foot_sensation_adequate_for_walking",
    label: "Foot sensation adequate for walking",
    categoryId: "health_wellness",
    lookFor:
      "Ask about numbness/tingling in the feet (common with diabetes) and check footwear fit; test light-touch sensation if comfortable doing so.",
    excellent: "Normal foot sensation reported and observed; well-fitting, supportive footwear worn.",
    acceptable: "Mild reduced sensation noted, but the elder compensates with careful footing and appropriate footwear.",
    unsafe:
      "Significant numbness (e.g., diabetic neuropathy) combined with unsafe footwear (loose chappals, no back strap), increasing fall/injury risk.",
    naWhen: "No known diabetes, neuropathy, or foot sensation concerns.",
    tip: "Loose-backed slippers/chappals are extremely common at home in India and are a frequent contributor when combined with reduced foot sensation.",
  },

  // ── 4. Activities of Daily Living (ADL) ─────────────────────────────────
  {
    id: "adl_bathing_independently_or_with_plan",
    label: "Bathing independently or with plan",
    categoryId: "adl",
    lookFor:
      "Ask/observe how bathing actually happens day to day: fully alone, with setup help, or with a caregiver present throughout.",
    excellent:
      "Bathes independently and safely, or has a consistent, safe, dignity-preserving plan (aide, shower chair, grab bars) that's actually followed.",
    acceptable:
      "Manages with some help (someone starts the water, stays nearby) that is generally reliable though informal.",
    unsafe: "Bathes alone despite high fall risk, or the stated 'plan' isn't actually happening consistently.",
    naWhen: "Rarely applicable — only if bathing is fully outsourced to a clinical setting outside this home.",
  },
  {
    id: "adl_dressing_independently_or_with_plan",
    label: "Dressing independently or with plan",
    categoryId: "adl",
    lookFor: "Ask about dressing, including fasteners (buttons, hooks, sari pins), footwear, and how much help is needed.",
    excellent:
      "Dresses fully independently, or has a reliable plan (family help, adaptive clothing, seated dressing) that maintains dignity and safety.",
    acceptable:
      "Manages most dressing alone but needs occasional help with specific items (blouse hooks, back zips, saris).",
    unsafe:
      "Cannot dress adequately and no consistent help arrangement exists, resulting in inappropriate or unsafe clothing/footwear.",
    naWhen: "Rarely applicable — only if fully covered by a live-in caregiver with a clear routine already in place.",
  },
  {
    id: "adl_toileting_independently_or_with_plan",
    label: "Toileting independently or with plan",
    categoryId: "adl",
    lookFor:
      "Ask about the full toileting sequence: getting there, transferring, hygiene, clothing, and returning — including at night.",
    excellent:
      "Manages toileting independently and safely, or has a reliable plan (commode, caregiver assistance, night routine) covering all steps including hygiene.",
    acceptable: "Manages with some help or extra time, without major incidents, though not fully independent.",
    unsafe:
      "Struggles with toileting and no reliable plan exists — risk of accidents, unsafe self-transfer, or hygiene lapses.",
    naWhen: "Not typically applicable — toileting support needs almost always apply in some form.",
  },
  {
    id: "adl_eating_feeding_independence",
    label: "Eating / feeding independence",
    categoryId: "adl",
    lookFor:
      "Watch or ask about a meal: can the elder bring food to mouth, use utensils/hands appropriately, chew and swallow safely?",
    excellent: "Eats independently and safely (setup like cutting food is fine); no choking or spillage concerns.",
    acceptable: "Needs some help (cutting food, opening containers, occasional reminders) but feeds self with utensils/hands.",
    unsafe:
      "Cannot feed self safely, shows signs of choking/aspiration risk, or is fully dependent with no consistent feeding support.",
    naWhen: "Not applicable — rarely N/A since eating is a universal ADL.",
  },
  {
    id: "adl_transfer_mobility_for_adls",
    label: "Transfer / mobility for ADLs",
    categoryId: "adl",
    lookFor:
      "Assess the elder's movement across the full care routine — e.g., bedroom to bathroom for bathing and back, plus getting to the toilet and dining area — not just one isolated transfer.",
    excellent:
      "Moves safely and independently (or with an appropriate device) through the full sequence of daily-care-related movement without strain or risk.",
    acceptable:
      "Manages these movements with cueing, a device, or light hands-on help, without falls or excessive effort.",
    unsafe:
      "High fall/strain risk moving between care locations, or cannot complete the sequence without unsafe effort or full lifting.",
    naWhen: "Elder is fully immobile and all care is delivered at the bedside (no movement between locations occurs).",
    tip: "This is broader than \u201cTransfers bed/chair safely\u201d under Mobility — that item is only the bed and chair mechanics; this one is the whole ADL-related movement journey around the home.",
  },
  {
    id: "adl_personal_hygiene_maintained",
    label: "Personal hygiene maintained",
    categoryId: "adl",
    lookFor:
      "Observe general grooming (hair, nails, oral care, skin, clothing cleanliness) as a proxy for whether hygiene routines are actually happening.",
    excellent: "Grooming, oral care, and cleanliness are well maintained, whether independently or with consistent help.",
    acceptable: "Generally acceptable hygiene with occasional lapses (a missed shave, slightly unkempt) that aren't a health risk.",
    unsafe:
      "Visible neglect — poor oral care, unwashed hair/body, dirty clothing — suggesting missing support or self-neglect.",
    naWhen: "Not applicable — rarely N/A since hygiene maintenance is universal.",
  },

  // ── 5. Instrumental ADLs (IADL) ─────────────────────────────────────────
  {
    id: "iadl_manages_medications_schedule",
    label: "Manages medications schedule",
    categoryId: "iadl",
    lookFor: "Ask how doses are tracked/reminded (pillbox, alarm, family call) and check for missed or doubled doses recently.",
    excellent:
      "Reliable system (pill organizer, alarms, or a caregiver) ensures correct doses at correct times with no recent errors.",
    acceptable: "Manages reasonably well but has had occasional missed/late doses without serious consequence.",
    unsafe: "Frequent missed, doubled, or wrong-time doses with no system in place to catch errors.",
    naWhen: "Elder takes no scheduled medications.",
  },
  {
    id: "iadl_prepares_or_receives_meals_safely",
    label: "Prepares or receives meals safely",
    categoryId: "iadl",
    lookFor:
      "Ask who cooks, whether the elder can safely use the stove/appliances if they cook, or how meals are otherwise reliably delivered (family, cook, tiffin service).",
    excellent:
      "Meals are prepared safely (by the elder if capable, or reliably by family/cook/tiffin service) with no missed meals.",
    acceptable:
      "Meals happen but with some gaps or reliance on an inconsistent arrangement (e.g., depends on whoever's free that day).",
    unsafe:
      "Elder attempts unsafe cooking (forgotten burners, unsafe knife use), or meals are frequently missed/inadequate with no backup plan.",
    naWhen: "Not typically applicable — nearly everyone needs some meal arrangement.",
    tip: "In Hyderabad, tiffin/dabba services and part-time cooks are common and count as a valid safe arrangement — confirm reliability, not just existence.",
  },
  {
    id: "iadl_handles_shopping_errands",
    label: "Handles shopping / errands",
    categoryId: "iadl",
    lookFor:
      "Ask how groceries, medicines, and errands are handled — self, family, online delivery (grocery/pharmacy apps), or a domestic helper.",
    excellent: "Shopping/errands are consistently handled, whether by the elder or a reliable arrangement (family, helper, delivery apps).",
    acceptable:
      "Handled adequately but depends on occasional/ad-hoc help without a firm backup if that person is unavailable.",
    unsafe: "No reliable way to get groceries/medicines, resulting in shortages, expired supplies, or missed medication refills.",
    naWhen: "Rarely applicable — mark N/A only if this is fully and permanently outsourced with no elder involvement expected.",
  },
  {
    id: "iadl_manages_finances_or_has_help",
    label: "Manages finances or has help",
    categoryId: "iadl",
    lookFor:
      "Ask who pays bills, manages bank accounts/pension, and whether the elder is vulnerable to financial confusion or exploitation.",
    excellent:
      "Finances are managed competently (by the elder or with trusted family help/power of attorney); bills are paid on time; no confusion or vulnerability signs.",
    acceptable:
      "Generally managed but with some reliance on family, or occasional missed payments/mild confusion without serious consequence.",
    unsafe:
      "Elder cannot manage finances and no help is in place, or there are signs of confusion, missed critical payments, or potential exploitation.",
    naWhen:
      "Rarely applicable — mark N/A only if finances are fully and appropriately handled under a documented legal arrangement not needing review here.",
  },
  {
    id: "iadl_uses_transportation_safely",
    label: "Uses transportation safely",
    categoryId: "iadl",
    lookFor: "Ask how the elder gets to appointments, temple, or social visits — self-driving, auto/cab, family, or a caregiver escort.",
    excellent:
      "Safe, reliable transportation arrangement in place (self if still safe to drive/ride, or consistent family/cab/escort support).",
    acceptable: "Manages trips but with some inconvenience or dependency on availability of others; no safety incidents.",
    unsafe:
      "Elder drives/rides unsafely (e.g., cognitive or vision concerns while still driving) or has no reliable way to leave the home for necessary trips.",
    naWhen: "Elder does not need to travel outside the home for any reason (fully home-based care and services).",
  },
  {
    id: "iadl_light_housework_manageable",
    label: "Light housework manageable",
    categoryId: "iadl",
    lookFor: "Ask about tidying, laundry, and basic upkeep — who does it and whether it's actually getting done.",
    excellent: "Light housework is handled well, whether by the elder or reliably by family/domestic help.",
    acceptable: "Housework happens but is inconsistent, or the home shows mild neglect without hygiene/safety consequences.",
    unsafe: "Housework has stopped entirely, leading to clutter, hygiene issues, or conditions that add fall/health risk.",
    naWhen: "Not typically applicable — nearly all households need some housework arrangement.",
  },

  // ── 6. Cognitive & Emotional Wellness ───────────────────────────────────
  {
    id: "cognitive_emotional_orientation_to_person_place_time",
    label: "Orientation to person/place/time",
    categoryId: "cognitive_emotional",
    lookFor: "Gently ask the date, where they are, and confirm they recognize familiar family members during the visit.",
    excellent: "Elder is fully oriented — knows roughly the date/day, recognizes their home and familiar people.",
    acceptable: "Mild disorientation (e.g., unsure of the exact date) but generally knows people and place correctly.",
    unsafe:
      "Significant disorientation — doesn't recognize home or close family, or is confused about basic time/place with safety implications.",
    naWhen: "Not applicable — this should be assessed for every elder regardless of baseline cognition.",
    tip: "Ask conversationally rather than as a test — e.g., 'What did you have for lunch today?' feels less clinical than a formal quiz.",
  },
  {
    id: "cognitive_emotional_mood_stable_no_untreated_depression",
    label: "Mood stable / no untreated depression",
    categoryId: "cognitive_emotional",
    lookFor:
      "Ask about mood, interest in usual activities, sleep, and appetite; watch for withdrawal or hopeless statements during the visit.",
    excellent:
      "Mood appears stable and engaged; no signs of untreated depression, or existing depression is being actively treated.",
    acceptable: "Some low mood or reduced interest noted, but not severe, and family is aware and attentive.",
    unsafe:
      "Signs of significant untreated depression (withdrawal, hopelessness, major appetite/sleep change) with no support in place.",
    naWhen: "Not applicable — mood should be assessed for every elder.",
  },
  {
    id: "cognitive_emotional_memory_adequate_for_daily_safety",
    label: "Memory adequate for daily safety",
    categoryId: "cognitive_emotional",
    lookFor:
      "Ask about recent forgetfulness relevant to safety — missed medications, repeated questions, forgetting appliances on, getting lost nearby.",
    excellent: "Memory is adequate for safe daily functioning; occasional normal forgetfulness with no safety impact.",
    acceptable: "Some memory lapses affect daily tasks, but they're caught/corrected by routines or family before causing harm.",
    unsafe:
      "Memory lapses have caused or nearly caused safety incidents (left the stove on, wandered and got lost, repeated dangerous medication errors).",
    naWhen: "Not applicable — should be assessed for every elder.",
  },
  {
    id: "cognitive_emotional_judgment_safe_for_leaving_stove_doors",
    label: "Judgment safe for leaving stove/doors",
    categoryId: "cognitive_emotional",
    lookFor:
      "Ask specifically about stove/gas shut-off habits, door/lock security at night, and any history of leaving hazards unaddressed.",
    excellent:
      "Consistently safe judgment — turns off stove/gas reliably, locks doors appropriately, recognizes and avoids obvious hazards.",
    acceptable: "Generally safe judgment with rare lapses that family monitors and corrects without incident.",
    unsafe:
      "Has left burners on, left doors unlocked/open at night, or otherwise shown an inability to recognize or respond to danger.",
    naWhen: "Elder never has independent access to the stove or door locks (fully supervised at all times).",
  },
  {
    id: "cognitive_emotional_social_engagement_present",
    label: "Social engagement present",
    categoryId: "cognitive_emotional",
    lookFor: "Ask about regular social contact — visitors, phone/video calls, community or religious gatherings, neighbors.",
    excellent:
      "Regular, meaningful social engagement (family visits, calls, community/temple activities) that the elder enjoys.",
    acceptable: "Some social contact exists but is infrequent, or the elder expresses mild loneliness.",
    unsafe: "Elder is largely isolated with little to no regular social contact, showing signs of loneliness or withdrawal.",
    naWhen: "Not applicable — social engagement should be assessed for every elder.",
  },
  {
    id: "cognitive_emotional_safe_from_wandering_getting_lost",
    label: "Safe from wandering / getting lost",
    categoryId: "cognitive_emotional",
    lookFor:
      "Ask family whether the elder has left home alone unexpectedly, got lost, or tries to go out at night; check whether the main door has any alert and whether they carry ID with a contact number.",
    excellent:
      "No wandering or getting lost, and no exit-seeking at any time of day.",
    acceptable:
      "Occasional confusion about going out, or one past episode, but someone is usually home and the door is watched.",
    unsafe:
      "Has wandered or got lost, or tries to leave at night, with no door alert, locator or supervision plan.",
    naWhen: "Elder is bed-bound or cannot leave the home without help.",
  },

  // ── 7. Emergency Preparedness ───────────────────────────────────────────
  {
    id: "emergency_emergency_contacts_posted",
    label: "Emergency contacts posted",
    categoryId: "emergency",
    lookFor:
      "Look for a visible, up-to-date list of emergency numbers (family, doctor, ambulance, neighbor) near the phone or front door.",
    excellent: "Clear, current, visible emergency contact list posted where the elder and any helper can quickly find it.",
    acceptable: "Contacts are known/saved in a phone but not physically posted anywhere visible.",
    unsafe: "No accessible record of emergency contacts anywhere, and the elder cannot recall key numbers if asked.",
    naWhen: "Not applicable — every home should have this regardless of the elder's own capability.",
    tip: "In Hyderabad, include the local ambulance number (108), the family doctor, and a nearby neighbor — not just family members who may be far away.",
  },
  {
    id: "emergency_sos_alert_method_available",
    label: "SOS / alert method available",
    categoryId: "emergency",
    lookFor:
      "Ask the elder to demonstrate how they'd call for help right now — phone on person, pendant, intercom, or shouting to a neighbor.",
    excellent:
      "A reliable, tested alert method (phone always on person, medical alert pendant, or intercom) that the elder can actually use if they fall or feel unwell.",
    acceptable: "A method exists (e.g., a phone in the next room) but isn't always within immediate reach.",
    unsafe:
      "No workable way to call for help if alone — phone often out of reach, no pendant/intercom, no reliable neighbor plan.",
    naWhen: "Elder is never alone even briefly (24/7 attended care).",
  },
  {
    id: "emergency_evacuation_path_understood",
    label: "Evacuation path understood",
    categoryId: "emergency",
    lookFor:
      "Ask the elder/family to describe how they'd exit the home quickly in a fire or emergency, and check the path is actually walkable.",
    excellent: "Elder and family both know a clear, walkable evacuation route, and it's free of obstacles.",
    acceptable: "A route exists and is generally understood, though not rehearsed or slightly cluttered.",
    unsafe:
      "No clear evacuation plan, or the only route is blocked, requires stairs the elder can't manage, or is unknown to the elder.",
    naWhen: "Not typically applicable — every home needs a basic evacuation understanding.",
  },
  {
    id: "emergency_first_aid_flashlight_accessible",
    label: "First aid / flashlight accessible",
    categoryId: "emergency",
    lookFor:
      "Check for a basic first-aid kit and a working flashlight/torch (or reliable power backup light) that's easy to locate in the dark.",
    excellent: "A stocked first-aid kit and a working, easy-to-find flashlight or backed-up light source are both readily accessible.",
    acceptable: "One of the two is present and adequate; the other is missing or hard to locate quickly.",
    unsafe: "Neither a first-aid kit nor a working flashlight/backup light can be located when asked.",
    naWhen: "Rarely applicable — basic first aid and light access is a universal need.",
    tip: "Given frequent power cuts in some Hyderabad areas, a charged torch or inverter-backed light near the bed is especially important.",
  },
  {
    id: "emergency_family_response_plan_documented",
    label: "Family response plan documented",
    categoryId: "emergency",
    lookFor: "Ask who would respond first in an emergency, how they'd be reached, and whether this is written down or just assumed.",
    excellent:
      "A clear, documented plan exists — who responds, in what order, with backup contacts if the primary person is unreachable.",
    acceptable: "Family generally knows who would respond, though it isn't written down formally.",
    unsafe:
      "No clear plan — family is unsure who would respond, or the only responder is often unreachable (e.g., abroad with no local backup).",
    naWhen: "Not typically applicable — every home benefits from having this defined.",
  },

  // ── 8. Home Condition & Maintenance ─────────────────────────────────────
  {
    id: "home_condition_no_major_structural_hazards",
    label: "No major structural hazards",
    categoryId: "home_condition",
    lookFor: "Look for visible cracks, sagging ceilings, unstable balconies/parapets, or unsafe stair structures.",
    excellent: "No visible structural hazards; the home has been checked and is structurally sound.",
    acceptable: "Minor cosmetic cracks or wear noted, with no immediate structural concern.",
    unsafe:
      "Visible significant cracks, sagging structures, unstable railings/parapets, or other hazards posing real danger.",
    naWhen: "Not applicable — should be assessed for every home.",
  },
  {
    id: "home_condition_electrical_outlets_wiring_safe",
    label: "Electrical outlets/wiring safe",
    categoryId: "home_condition",
    lookFor: "Check visible wiring, outlets, and switches for exposed wires, overloaded extension boards, or scorch marks.",
    excellent: "Wiring and outlets are in good condition; no overloaded extension boards or exposed wires anywhere accessible.",
    acceptable: "Generally safe, but one extension board is a bit overloaded or an outlet is slightly worn without immediate danger.",
    unsafe: "Exposed/frayed wiring, badly overloaded extension boards, or scorch marks/burning smell near outlets.",
    naWhen: "Not applicable — should be assessed for every home.",
    tip: "Multi-socket extension boards daisy-chained together are extremely common in Indian homes and a frequent fire-risk flag.",
  },
  {
    id: "home_condition_damp_mold_controlled",
    label: "Damp / mold controlled",
    categoryId: "home_condition",
    lookFor:
      "Check walls/ceilings, especially in bathrooms and monsoon-exposed areas, for damp patches, peeling paint, or visible mold/mildew.",
    excellent: "No significant damp or mold; any past monsoon seepage has been properly repaired.",
    acceptable:
      "Minor damp patches or seasonal seepage exist but aren't actively worsening or causing respiratory complaints.",
    unsafe: "Active mold growth, persistent damp walls, or damp-related respiratory symptoms in the elder.",
    naWhen: "Not applicable — should be assessed for every home.",
    tip: "Check especially after the monsoon season — seepage from terraces or bathroom walls is a common issue in older Hyderabad buildings.",
  },
  {
    id: "home_condition_plumbing_reliable",
    label: "Plumbing reliable",
    categoryId: "home_condition",
    lookFor: "Ask about water supply reliability, leaks, and whether the geyser/taps function properly.",
    excellent: "Plumbing works reliably — no leaks, consistent water supply, functioning geyser/taps.",
    acceptable: "Minor issues (a slow drain, occasional low water pressure) that don't disrupt daily use.",
    unsafe: "Significant leaks, unreliable water supply affecting bathing/toileting, or a non-functioning geyser in cold weather.",
    naWhen: "Not applicable — should be assessed for every home.",
  },
  {
    id: "home_condition_repairs_backlog_acceptable",
    label: "Repairs backlog acceptable",
    categoryId: "home_condition",
    lookFor: "Ask about pending repairs the family has been putting off and how long they've been outstanding.",
    excellent: "No significant pending repairs, or all safety-relevant repairs are completed promptly.",
    acceptable: "Some non-urgent repairs are pending but nothing safety-critical is being delayed.",
    unsafe:
      "Safety-relevant repairs (grab bars, wiring, structural issues) have been known about for a long time and remain undone.",
    naWhen: "Not applicable — should be assessed for every home.",
  },

  // ── 9. Technology Readiness ─────────────────────────────────────────────
  {
    id: "technology_can_use_phone_for_emergencies",
    label: "Can use phone for emergencies",
    categoryId: "technology",
    lookFor:
      "Ask the elder to show how they'd call a family member or emergency number right now; check for vision/dexterity barriers.",
    excellent: "Elder can independently make and answer calls, including to emergency contacts, without confusion.",
    acceptable:
      "Can make calls with occasional help (e.g., needs someone to dial the first time, or uses a large-button/simplified phone).",
    unsafe:
      "Cannot operate a phone to call for help even with a simple/large-button device, and no alternative alert method exists.",
    naWhen: "Elder is never without a caregiver capable of making calls on their behalf.",
  },
  {
    id: "technology_video_call_capable_self_or_family",
    label: "Video call capable (self or family)",
    categoryId: "technology",
    lookFor:
      "Ask if the elder or a present caregiver can start/answer a video call (e.g., WhatsApp) so distant family can check in visually.",
    excellent: "Elder or an on-site caregiver can reliably start/answer video calls for family check-ins.",
    acceptable: "Video calling is possible but needs setup help each time from a family member or helper.",
    unsafe: "No one on-site can manage video calls, cutting off a key channel for remote family monitoring and reassurance.",
    naWhen: "All family lives locally with frequent in-person visits, and remote video check-ins aren't needed.",
  },
  {
    id: "technology_smart_safety_devices_appropriate",
    label: "Smart safety devices appropriate",
    categoryId: "technology",
    lookFor:
      "Check whether any smart safety devices (fall-detection wearable, smart plugs, camera, medical alert button) are in use and suited to the elder's needs and comfort.",
    excellent: "Appropriate smart safety devices are in place, working, and comfortably accepted by the elder.",
    acceptable: "Some device is present but underused, or a suitable device has been identified but not yet installed.",
    unsafe: "No smart safety devices despite a clear need (e.g., living alone with fall risk) and no plan to introduce any.",
    naWhen: "Elder has 24/7 in-person supervision and no additional device is needed.",
  },
  {
    id: "technology_medication_reminder_tech_if_needed",
    label: "Medication reminder tech if needed",
    categoryId: "technology",
    lookFor:
      "If the elder struggles with medication timing, check for reminder tech (phone alarms, automated pill dispenser, family reminder calls).",
    excellent: "A reliable reminder system (app, alarm, smart dispenser, or scheduled family calls) is in place and working.",
    acceptable: "Some reminder method exists but is informal or occasionally missed without major consequence.",
    unsafe: "Elder has known medication timing issues and no reminder system of any kind is in place.",
    naWhen: "Elder manages medication timing reliably without any reminder support, or takes no scheduled medications.",
  },
  {
    id: "technology_wi_fi_power_backup_considered",
    label: "Wi\u2011Fi / power backup considered",
    categoryId: "technology",
    lookFor:
      "Ask about internet reliability (for video calls/alerts) and power backup (inverter/generator) for outages, especially for any powered medical equipment.",
    excellent:
      "Reliable Wi\u2011Fi/data connectivity plus adequate power backup (inverter/generator) covering essential lights, fans, and any medical devices.",
    acceptable:
      "Connectivity and backup exist but are limited (e.g., inverter covers lights only, not the geyser or an oxygen concentrator).",
    unsafe:
      "No power backup for an area with frequent outages, especially where the elder depends on powered medical equipment, or no reliable internet for emergency video contact.",
    naWhen: "Area has stable power and no critical devices depend on continuous electricity or connectivity.",
  },
  {
    id: "technology_light_switches_easy_to_reach_and_operate",
    label: "Light switches easy to reach and operate",
    categoryId: "technology",
    lookFor:
      "Walk the bedroom, bathroom and hallway: can the elder reach and work each light switch from the bed, doorway or a seated position, including at night?",
    excellent:
      "Switches reachable at the doorway and bedside, easy to press, or lights come on by motion or voice.",
    acceptable:
      "Most switches are reachable but one or two key ones (bedside, bathroom) are awkward or far.",
    unsafe:
      "Must walk across a dark room to turn on a light, or cannot work the switches (height, stiffness, small rocker).",
    naWhen: "A carer is always present to switch lights on and off.",
  },
  {
    id: "technology_home_secure_locks_visitor_check",
    label: "Home secure (locks, visitor check)",
    categoryId: "technology",
    lookFor:
      "Check the main door lock and whether the elder can see who is outside before opening (peephole, chain, video doorbell). Ask about past break-ins or strangers at the door.",
    excellent:
      "Sturdy locks in use, a way to see visitors before opening, and the elder does not open to strangers.",
    acceptable:
      "Locks fine but no easy way to check visitors, or the elder sometimes opens without checking.",
    unsafe:
      "Broken or weak locks, door often left open, or the elder lives alone and regularly opens to unknown callers.",
    naWhen: "Never at home alone; a carer or family member always answers the door.",
  },

  // ── 10. Family & Caregiver Support ──────────────────────────────────────
  {
    id: "family_support_primary_caregiver_family_identified",
    label: "Primary caregiver / family identified",
    categoryId: "family_support",
    lookFor: "Ask who is considered the main responsible person for the elder's day-to-day wellbeing, and confirm that person agrees.",
    excellent: "A clear primary caregiver is identified, known to the elder and family, and actively engaged.",
    acceptable: "A primary caregiver is informally identified but role/expectations aren't fully clarified among family members.",
    unsafe: "No one is clearly responsible, or responsibility is disputed/unclear among family members, risking gaps in care.",
    naWhen: "Not applicable — every elder's care arrangement should have this defined.",
  },
  {
    id: "family_support_check_in_frequency_adequate",
    label: "Check-in frequency adequate",
    categoryId: "family_support",
    lookFor: "Ask how often the elder is checked on (in person or by phone) and whether that matches their actual risk level.",
    excellent: "Check-in frequency is appropriate to the elder's risk level (e.g., daily calls, frequent visits) and consistently happens.",
    acceptable: "Check-ins happen but slightly less often than ideal, or are occasionally missed without consequence so far.",
    unsafe:
      "Check-ins are rare or unreliable relative to the elder's risk level, leaving long gaps where a problem could go unnoticed.",
    naWhen: "Elder has 24/7 in-person caregiving, making separate check-ins unnecessary.",
  },
  {
    id: "family_support_nri_remote_family_plan_if_applicable",
    label: "NRI / remote family plan if applicable",
    categoryId: "family_support",
    lookFor:
      "If children/family live outside Hyderabad or abroad, ask specifically who checks in, how often, and who would physically respond locally in an emergency.",
    excellent:
      "A clear plan exists — regular remote check-ins plus a designated local responder (family, ECM, or trusted neighbor) for emergencies.",
    acceptable: "Remote family stays in touch but the local emergency-response piece is informal or not fully tested.",
    unsafe: "Remote family is largely disengaged, or there is no one who could respond locally within a reasonable time in an emergency.",
    naWhen: "All immediate family lives locally and is actively engaged, so a remote plan isn't needed.",
    tip: "This is very common in Hyderabad with NRI children — probe specifically for the *local* emergency responder, not just who calls most often.",
  },
  {
    id: "family_support_caregiver_stress_manageable",
    label: "Caregiver stress manageable",
    categoryId: "family_support",
    lookFor: "Ask the primary caregiver directly about their own stress, sleep, health, and whether they get any respite.",
    excellent: "Caregiver reports manageable stress, gets periodic respite/support, and shows no signs of burnout.",
    acceptable: "Some caregiver strain is evident, but they are coping and aware of resources if needed.",
    unsafe: "Caregiver shows clear signs of burnout, exhaustion, or declining health, with no respite or support in place.",
    naWhen: "Care is fully provided by paid professional staff with organizational support (no informal family caregiver strain applicable).",
  },
  {
    id: "family_support_advance_directive_decision_maker_known",
    label: "Advance directive / decision-maker known",
    categoryId: "family_support",
    lookFor: "Ask who would make medical/financial decisions if the elder couldn't, and whether this is documented (POA, nominee, advance directive).",
    excellent: "A clear, documented decision-maker (power of attorney, nominee, or advance directive) is established and known to the family.",
    acceptable: "Family has an informal understanding of who would decide, but nothing is formally documented.",
    unsafe: "No one is identified or agreed upon as decision-maker, risking confusion or conflict during a medical crisis.",
    naWhen:
      "Elder is fully capable and family considers this premature to formalize now — note as a soft N/A with a follow-up recommendation.",
  },
  {
    id: "family_support_willing_to_engage_ecm_if_recommended",
    label: "Willing to engage ECM if recommended",
    categoryId: "family_support",
    lookFor: "Ask whether the family would be open to an Eldercare/Care Manager (ECM) coordinating services if the assessment recommends it.",
    excellent: "Family is receptive and would readily engage an ECM if recommended, understanding the value of coordinated support.",
    acceptable: "Family is undecided or has some hesitation but is open to discussing it further.",
    unsafe: "Family is firmly resistant to any outside coordination even where significant needs are identified, leaving gaps unaddressed.",
    naWhen: "No ECM-level coordination need is anticipated based on the assessment findings.",
  },

  // ── 11. Financial & Government Benefits ─────────────────────────────────
  {
    id: "financial_benefits_income_pension_status_known",
    label: "Income / pension status known",
    categoryId: "financial_benefits",
    lookFor: "Ask about the elder's income sources — pension, EPFO, rental income, family support — and whether it's sufficient and reliable.",
    excellent: "Income/pension status is clear, documented, and sufficient for the elder's needs.",
    acceptable: "Income is known and generally adequate, though slightly tight or informally tracked.",
    unsafe: "Income situation is unclear, insufficient for basic needs, or family cannot confirm how the elder is financially supported.",
    naWhen: "Not applicable — financial status should be understood for every elder, even if just to confirm it's not a concern.",
  },
  {
    id: "financial_benefits_health_insurance_schemes_reviewed",
    label: "Health insurance / schemes reviewed",
    categoryId: "financial_benefits",
    lookFor:
      "Ask whether the elder has health insurance or is enrolled in relevant government schemes (e.g., Aarogyasri/Ayushman Bharat where eligible) and whether coverage has been reviewed.",
    excellent: "Health insurance or eligible government scheme coverage is in place, reviewed for adequacy, and understood by the family.",
    acceptable: "Some coverage exists but hasn't been reviewed recently, or eligibility for additional schemes hasn't been checked.",
    unsafe: "No health insurance or scheme coverage at all, leaving the elder exposed to major medical costs with no plan.",
    naWhen: "Family has already confirmed coverage is adequate through a recent independent review.",
  },
  {
    id: "financial_benefits_eligible_government_benefits_identified",
    label: "Eligible government benefits identified",
    categoryId: "financial_benefits",
    lookFor:
      "Ask whether senior citizen benefits (state pension schemes, rail/bus concessions, tax benefits, utility concessions) have been checked and claimed.",
    excellent: "Family has identified and is actively using all benefits the elder is eligible for.",
    acceptable: "Some benefits are used, but eligibility for others hasn't been fully explored.",
    unsafe: "No government benefits have been explored or claimed despite likely eligibility, leaving available support unused.",
    naWhen: "Elder is not eligible for any additional government benefits beyond what's already secured.",
  },
  {
    id: "financial_benefits_documents_available_for_applications",
    label: "Documents available for applications",
    categoryId: "financial_benefits",
    lookFor:
      "Check whether key documents (Aadhaar, age proof, income certificate, medical records, bank passbook) are organized and accessible for any applications.",
    excellent: "All key documents are organized, up to date, and easily accessible when needed.",
    acceptable: "Most documents exist but are scattered, or a couple are missing/need renewal.",
    unsafe: "Key documents are missing or lost, which would block access to benefits, insurance claims, or emergency care.",
    naWhen: "No applications or claims are anticipated that would require these documents.",
  },
  {
    id: "financial_benefits_budget_for_home_improvements_realistic",
    label: "Budget for home improvements realistic",
    categoryId: "financial_benefits",
    lookFor: "Ask about the family's willingness and ability to fund recommended safety improvements (grab bars, ramps, etc.) from this assessment.",
    excellent: "Family has a realistic, confirmed budget and readiness to proceed with recommended improvements.",
    acceptable: "Family is willing but budget is uncertain, or would need to be planned/phased over time.",
    unsafe: "No budget or willingness exists for safety-critical improvements, even where risk is significant.",
    naWhen: "No home improvements are being recommended for this assessment.",
  },

  // ── 12. Lifestyle & Social Engagement ───────────────────────────────────
  {
    id: "lifestyle_day_structure_routine_present",
    label: "Day structure / routine present",
    categoryId: "lifestyle",
    lookFor:
      "Ask the elder to describe a typical day — wake time, meals, activities, rest — and note whether there's a consistent, meaningful structure.",
    excellent: "A consistent, meaningful daily routine is in place that the elder finds satisfying and stabilizing.",
    acceptable: "Some routine exists but is loose, or the elder describes long unstructured stretches without distress.",
    unsafe: "No discernible routine; days are described as aimless, isolating, or distressing to the elder.",
    naWhen: "Not applicable — every elder's daily life should be assessed for structure.",
  },
  {
    id: "lifestyle_social_contacts_weekly",
    label: "Social contacts weekly",
    categoryId: "lifestyle",
    lookFor:
      "Ask how many different people (beyond the immediate household) the elder interacts with in a typical week, in person or by phone/video.",
    excellent: "Regular weekly contact with multiple people — family, friends, neighbors, community — that the elder values.",
    acceptable: "Some weekly contact exists but is limited to one or two people, or feels occasional.",
    unsafe: "Little to no social contact beyond the household in a typical week, with signs of loneliness.",
    naWhen: "Not applicable — social contact should be assessed for every elder.",
  },
  {
    id: "lifestyle_meaningful_activities_available",
    label: "Meaningful activities available",
    categoryId: "lifestyle",
    lookFor: "Ask about hobbies, religious/spiritual practice, TV/reading, or other activities the elder finds enjoyable or purposeful.",
    excellent: "Elder regularly engages in activities they find meaningful and enjoyable (hobbies, prayer, reading, family roles).",
    acceptable: "Some activity exists but is limited, or the elder expresses mild boredom/lack of purpose.",
    unsafe: "Elder has no meaningful activity in their day, expressing boredom, purposelessness, or withdrawal.",
    naWhen: "Not applicable — meaningful activity should be assessed for every elder.",
  },
  {
    id: "lifestyle_outdoor_community_access",
    label: "Outdoor / community access",
    categoryId: "lifestyle",
    lookFor: "Ask how often the elder gets outside — a walk, the balcony, temple visits, community events — and what barriers exist.",
    excellent: "Elder regularly gets outside and engages with the community (temple, park, neighborhood, gatherings) as they wish.",
    acceptable: "Some outdoor/community access occurs but less often than the elder would like, due to mobility or transport limits.",
    unsafe: "Elder is essentially confined indoors with no outdoor or community access, which is affecting mood or health.",
    naWhen: "Elder has expressed a genuine, comfortable preference to stay indoors and shows no distress from this.",
  },
  {
    id: "lifestyle_sleep_environment_supportive",
    label: "Sleep environment supportive",
    categoryId: "lifestyle",
    lookFor: "Check the bedroom for comfortable temperature/ventilation, noise level, mattress condition, and ask about sleep quality.",
    excellent: "Sleep environment is comfortable (ventilation, noise, mattress) and the elder reports good, restful sleep.",
    acceptable: "Environment is adequate with a minor issue (a noisy area, a warm room without a fan) that doesn't seriously disrupt sleep.",
    unsafe: "Poor sleep environment (excessive heat/noise/poor mattress) and the elder reports consistently poor sleep as a result.",
    naWhen: "Not applicable — sleep environment should be assessed for every elder.",
  },
];

/** Lookup by exact item id first, then by exact (case-insensitive) label. */
export function trainingForItem(idOrLabel: string): AssessorItemTraining | undefined {
  const key = idOrLabel?.trim();
  if (!key) return undefined;

  const byId = ASSESSOR_ITEM_TRAINING.find((t) => t.id === key);
  if (byId) return byId;

  const lowerKey = key.toLowerCase();
  return ASSESSOR_ITEM_TRAINING.find((t) => t.label.toLowerCase() === lowerKey);
}

/** The "look for" text without its own "Look for" opener (avoids "Look for: Look for …"). */
export function lookForText(t: Pick<AssessorItemTraining, "lookFor">): string {
  const s = t.lookFor.replace(/^\s*look\s+for\s*:?\s*/i, "");
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

/** Multi-line assessor guidance suitable for a “?” help panel. */
export function formatTrainingHelp(t: AssessorItemTraining): string {
  const lines = [
    `Look for: ${lookForText(t)}`,
    `★ Excellent: ${t.excellent}`,
    `~ Acceptable: ${t.acceptable}`,
    `✕ Unsafe: ${t.unsafe}`,
    `— N/A: ${t.naWhen}`,
  ];
  if (t.tip?.trim()) lines.push(`Tip: ${t.tip.trim()}`);
  return lines.join("\n");
}

/** All training entries for a given KAA category id, in checklist order. */
export function trainingByCategoryId(categoryId: string): AssessorItemTraining[] {
  return ASSESSOR_ITEM_TRAINING.filter((t) => t.categoryId === categoryId);
}
