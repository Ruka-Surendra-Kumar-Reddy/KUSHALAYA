# Assessment finding → product links

Audit of 2026-10-09. 58 solutions × catalog products. **36 solutions changed, 60 links added,
29 removed, 49 products touched; EMG-006 Big-button emergency phone and SMT-012 GPS
locator wearable added to the catalog** (they were only in the shop price list).

## How recommendations are produced

1. Assessment ratings Risk/Needs attention → rubric item ids.
2. Solution library (`default_solutions.json`, stored per tenant in `workflow_config`)
   maps rubric items to solutions via `rubricItemIds` (`frontend/lib/livewell/improvement-plan.ts`).
3. Each catalog product lists the solutions it fixes in `solution_ids`; the quote draft takes
   every product whose `solution_ids` contains a plan solution
   (`product-recommendations.ts` → `productsForSolution`). `productCategories` on a solution is
   display text only.
4. The live catalog is the global `app_global_settings['home_safety_catalog']` row (seeded once
   from `default_catalog.json`). `backend/app/livewell/catalog_link_fixes.py` rewrites the links
   below on the first catalog load after deploy (marker `catalog_link_fixes`, now v3; a catalog
   already at v2 gets only the v3 additions, see below).
5. The rubric (questions) and the solution library are stored per tenant in `workflow_config`.
   `backend/app/livewell/rubric_gap_fixes.py` adds the 2026-10-11 questions and links to each
   tenant once, on the first rubric/solutions read (marker `workflow_config.rubric_gap_fixes`, v1).

Source of truth for the seed: `backend/app/livewell/data/Kushalaya_Configuration.xlsx`
(sheets 05_Products, 06_ProductSolutions) → `default_catalog.json` and
`frontend/lib/livewell/generated/catalog-from-workbook.json`; all three updated together.
Questions: sheets 02_AssessmentQuestions / 04_SolutionTriggers ↔ `default_rubric.json`
(generated from `frontend/lib/livewell/lwa-rubric.ts`) and `rubricItemIds` in
`default_solutions.json` (backend + frontend copies).

## 2026-10-11: questions added for findings no question raised

New questions (rating scale standard, not hidden; factory weights redistributed inside the
section so the total stays 100; live tenants get the neighbours' weight). Assessor help is in
`frontend/lib/livewell/assessor-item-training.ts` and on the live item (`help`).

| Question id | Section | Raises |
|---|---|---|
| `home_safety_bathroom_well_ventilated` "Bathroom well ventilated" | 1. Home Safety (Bath & wet areas) | LW-HS-BTH-010 |
| `health_wellness_bp_sugar_checked_regularly` "BP / sugar checked regularly" | 3. Health & Wellness (Clinical baseline) | LW-HL-MON-001 |
| `cognitive_emotional_safe_from_wandering_getting_lost` "Safe from wandering / getting lost" | 6. Cognitive & Emotional Wellness | LW-COG-WAN-001 |
| `technology_light_switches_easy_to_reach_and_operate` "Light switches easy to reach and operate" | 9. Technology Readiness | LW-TECH-LIT-001 |
| `technology_home_secure_locks_visitor_check` "Home secure (locks, visitor check)" | 9. Technology Readiness | LW-TECH-SEC-001 |

Existing questions linked (reused): `emergency_sos_alert_method_available` and
`technology_can_use_phone_for_emergencies` → LW-EMG-COM-001;
`technology_smart_safety_devices_appropriate` → LW-TECH-FAL-001.

Products moved from the shop-only list (`commerce.EXTRA_CATALOG`, now empty) into the
assessment catalog (new catalog type HLT "Health Monitoring"); `catalog_link_fixes` v3 adds them
to the live catalog if missing and appends missing links, without touching prices, images or
other products:

| Product | Solutions |
|---|---|
| BTH-012 Bath transfer bench | LW-HS-BTH-002, LW-HS-BTH-003 |
| BTH-013 Bathroom exhaust fan | LW-HS-BTH-010 |
| HLT-001 Digital BP monitor | LW-HL-MON-001 |
| HLT-002 Pulse oximeter | LW-HL-MON-001 |
| HLT-003 Glucometer with strips | LW-HL-MON-001 |
| HLT-004 Weekly pill organiser | LW-HL-MED-001, LW-COG-MEM-001 |

The shop "Suggested for you" list (`suggestions.py`) is separate: it uses `Product.fixes`
(rubric question ids set on the Products page) or name keywords, not these links.

## Not linked (no fitting product in the catalog)

- LW-HS-BED-004, LW-ADL-*, LW-FAM-LEG-001: no matching product.
- (Fixed 2026-10-11: ventilation, transfer bench, BP monitor / glucometer, and the
  wandering / emergency-call / LW-TECH-* questions — see above.)
- NUR-005/006/007 (wound, catheter, IV) and TRN-003 (airport) are no longer auto-suggested;
  they are ordered on need.

## Table

| Solution | Finding | Currently linked | Proposed | Reason |
|---|---|---|---|---|
| LW-HS-BTH-001 | Unsafe toilet transfer | SVC-002 Bathroom Safety Installation, BTH-001 Straight Grab Bar, BTH-004 Floor Supported Grab Bar, BTH-006 Raised Toilet Seat, BTH-007 Toilet Safety Frame | unchanged | keep |
| LW-HS-BTH-002 | Unsafe shower entry | SVC-002 Bathroom Safety Installation, BTH-001 Straight Grab Bar, BTH-002 L-Shaped Grab Bar, BTH-003 Foldable Grab Bar, BTH-010 Handheld Shower | SVC-002 Bathroom Safety Installation, BTH-001 Straight Grab Bar, BTH-002 L-Shaped Grab Bar, BTH-003 Foldable Grab Bar, BTH-009 Anti-slip Strips, BTH-010 Handheld Shower | add anti-slip strips for the wet shower step-in |
| LW-HS-BTH-003 | Unstable bathing position | SVC-002 Bathroom Safety Installation, BTH-005 Shower Chair | SVC-002 Bathroom Safety Installation, BTH-005 Shower Chair, BTH-010 Handheld Shower | add handheld shower (needed to bathe seated) |
| LW-HS-BTH-004 | Slippery bathroom floor | SVC-002 Bathroom Safety Installation, BTH-008 Anti-slip Floor Coating, BTH-009 Anti-slip Strips | unchanged | keep |
| LW-HS-BTH-011 | Hot water scald risk | BTH-011 Thermostatic Mixer / Temp Limit Valve | unchanged | keep |
| LW-HS-BTH-005 | Poor bathroom lighting | — | BED-004 Motion Night Light, HAL-001 Motion Sensor Light | was unmapped; motion lights for the bathroom |
| LW-HS-BTH-006 | No bathroom emergency alert | — | SMT-006 Wearable Care Alert Kit, SMT-011 Room SOS Button | was unmapped; room SOS button / wearable SOS |
| LW-HS-BTH-007 | Bathroom not accessible for walker/wheelchair | — | BTH-003 Foldable Grab Bar, EXT-002 Threshold / Wheelchair Ramp | was unmapped; threshold ramp + fold-up bar for wheelchair transfers |
| LW-HS-BTH-008 | Scald risk from hot water | — | BTH-011 Thermostatic Mixer / Temp Limit Valve | was unmapped; same thermostatic valve as LW-HS-BTH-011 |
| LW-HS-BTH-009 | Unsafe or inaccessible sink use | — | BTH-001 Straight Grab Bar | was unmapped; grab bar by the basin |
| LW-HS-BTH-010 | Poor bathroom ventilation | — | unchanged | keep |
| LW-HS-BED-001 | Unsafe bed transfer | SVC-003 Bedroom Safety Modifications, BED-001 Bed Rail, BED-002 Adjustable Bed, BED-003 Bed Risers, BED-005 Fall Mat, HM-006 Carpenter Visit | unchanged | keep |
| LW-HS-BED-002 | Poor night navigation to bathroom | SVC-003 Bedroom Safety Modifications, BED-004 Motion Night Light, HAL-001 Motion Sensor Light | SVC-003 Bedroom Safety Modifications, BED-004 Motion Night Light, HAL-001 Motion Sensor Light, HAL-002 LED Strip Lighting, HAL-003 Hallway Handrail | add LED strip + hallway handrail for the night route |
| LW-HS-BED-003 | Bedroom clutter / trip hazards | — | LIV-003 Anti-slip Rug Pad | was unmapped; anti-slip rug pads |
| LW-HS-BED-004 | Hard for responders to reach bed | — | unchanged | keep |
| LW-HS-BED-007 | Poor bedroom lighting | — | BED-004 Motion Night Light, HAL-002 LED Strip Lighting | was unmapped; bedroom lighting |
| LW-HS-ENT-001 | Uneven walkway | EXT-002 Threshold / Wheelchair Ramp, MOB-007 Portable Ramp | EXT-002 Threshold / Wheelchair Ramp, BAL-001 Anti-slip Outdoor Coating, MOB-007 Portable Ramp | add anti-slip outdoor coating (was wrongly on electrical) |
| LW-HS-ENT-004 | No accessible main entry | EXT-002 Threshold / Wheelchair Ramp, MOB-007 Portable Ramp | unchanged | keep |
| LW-HS-ENT-002 | No entrance handrail | EXT-001 Entrance / Stair Handrail | EXT-001 Entrance / Stair Handrail, BAL-002 Safety Railing Upgrade | add railing upgrade (was wrongly on plumbing) |
| LW-HS-ENT-003 | Poor entrance lighting | EXT-003 Outdoor Motion Light, EXT-004 Solar Security Light | unchanged | keep |
| LW-HS-STA-001 | Unsafe stairs | EXT-001 Entrance / Stair Handrail, KIT-001 Pull Down Shelf, KIT-002 Lazy Susan Organizer | BTH-009 Anti-slip Strips, EXT-001 Entrance / Stair Handrail | drop kitchen shelf/organiser; add anti-slip strips for steps |
| LW-HS-LIV-001 | Loose rugs / trip hazards in living areas | LIV-003 Anti-slip Rug Pad | unchanged | keep |
| LW-HS-LIV-002 | Unsafe furniture layout | LIV-004 High Stability Recliner Chair, HM-006 Carpenter Visit | unchanged | keep |
| LW-HS-LIV-003 | Sharp / glass coffee table hazard | LIV-001 Rounded Coffee Table, LIV-002 Furniture Corner Guards | unchanged | keep |
| LW-HS-LIV-004 | Electrical hazards | SMT-010 Smart Smoke Detector | SMT-010 Smart Smoke Detector, HM-001 Home Electrical Safety Check, HM-005 Electrician Visit (repair) | add electrical safety check + electrician |
| LW-HS-KIT-001 | Kitchen burn / fire hazard | HAL-001 Motion Sensor Light, HAL-002 LED Strip Lighting, HAL-003 Hallway Handrail, KIT-003 Gas Leak Detector, KIT-005 Fire Extinguisher | KIT-003 Gas Leak Detector, KIT-005 Fire Extinguisher | drop hallway lights/handrail (not kitchen fire items) |
| LW-HS-KIT-002 | Missing smoke or CO detectors | KIT-004 Smoke Detector, KIT-006 Carbon Monoxide Detector | KIT-004 Smoke Detector, KIT-006 Carbon Monoxide Detector, SMT-010 Smart Smoke Detector | add smart smoke detector |
| LW-MOB-WAL-001 | Unsteady gait | MOB-001 Walker, MOB-002 Rollator Walker, MOB-005 Walking Cane, MOB-006 Quad Cane, PHY-001 Physiotherapy Initial Assessment, PHY-002 Physiotherapy Home Session, PHY-003 Physiotherapy Monthly Package | unchanged | keep |
| LW-MOB-BAL-001 | Balance impairment | MOB-003 Wheelchair, MOB-004 Transfer Chair, PHY-001 Physiotherapy Initial Assessment, PHY-002 Physiotherapy Home Session, PHY-003 Physiotherapy Monthly Package | unchanged | keep |
| LW-MOB-WCH-001 | Home not wheelchair accessible | PHY-002 Physiotherapy Home Session | EXT-002 Threshold / Wheelchair Ramp, MOB-007 Portable Ramp | ramps, not physiotherapy, make the home accessible |
| LW-HL-MED-001 | Medication non-adherence | WEL-001 Wellness Visit (30–60 min), WEL-005 Grocery Assistance | SMT-007 Medication Reminder, WEL-001 Wellness Visit (30–60 min), WEL-003 Medicine Pickup, NUR-004 Injection at Home | drop grocery help; add medication reminder, medicine pickup, injections |
| LW-HL-MON-001 | No regular health monitoring | WEL-004 Doctor Visit Assistance, NUR-001 Nurse Visit, NUR-002 Home Nursing (10 hr), NUR-003 Home Nursing (24 hr), NUR-005 Wound Dressing, NUR-006 Catheter Change, NUR-007 IV Administration, DX-001 Doctor Home Visit, DX-002 Blood Collection at Home, DX-003 Lab Test (panel), DX-004 ECG at Home, TRN-001 Hospital Drop, TRN-002 Hospital Accompaniment | WEL-004 Doctor Visit Assistance, NUR-001 Nurse Visit, NUR-002 Home Nursing (10 hr), NUR-003 Home Nursing (24 hr), DX-001 Doctor Home Visit, DX-002 Blood Collection at Home, DX-003 Lab Test (panel), DX-004 ECG at Home | drop wound/catheter/IV procedures and hospital transport |
| LW-HL-NUT-001 | Poor nutrition or hydration | SMT-007 Medication Reminder, WEL-003 Medicine Pickup, NUR-001 Nurse Visit, NUR-004 Injection at Home | WEL-005 Grocery Assistance, NUR-001 Nurse Visit | drop medication items; add grocery assistance |
| LW-ADL-BAT-001 | Needs help bathing | WEL-007 Hygiene Visit, WEL-008 Caregiver (10 hr day), WEL-009 Caregiver (24 hr live-in), WEL-011 Personal Care / ADL Attendant (hourly), NUR-001 Nurse Visit, NUR-002 Home Nursing (10 hr), NUR-003 Home Nursing (24 hr) | unchanged | keep |
| LW-ADL-DRS-001 | Needs help dressing | WEL-008 Caregiver (10 hr day), WEL-009 Caregiver (24 hr live-in), WEL-011 Personal Care / ADL Attendant (hourly) | unchanged | keep |
| LW-IADL-MEAL-001 | Difficulty preparing meals | — | KIT-001 Pull Down Shelf, KIT-002 Lazy Susan Organizer | was unmapped; kitchen reach aids moved here from stairs |
| LW-IADL-SHOP-001 | Difficulty shopping | — | WEL-005 Grocery Assistance | was unmapped; grocery assistance |
| LW-COG-MEM-001 | Memory concerns | — | SMT-007 Medication Reminder, SMT-008 Voice Assistant | was unmapped; reminders |
| LW-COG-WAN-001 | Wandering risk | — | SMT-004 Motion Sensor, SMT-005 Door Sensor, SMT-006 Wearable Care Alert Kit, SMT-012 GPS locator wearable | was unmapped; door/motion sensors, GPS locator, wearable alert |
| LW-SOC-LON-001 | Social isolation | — | WEL-002 Companion Visit, WEL-006 Video Calling Training / Setup, WEL-013 Smartphone Setup | was unmapped; companion visits + video calling |
| LW-EMG-COM-001 | No reliable emergency call method | SVC-005 Medical Alert System Setup, EMG-001 Emergency Contact Board | SVC-005 Medical Alert System Setup, SMT-011 Room SOS Button, EMG-001 Emergency Contact Board, EMG-006 Big-button emergency phone | add room SOS button + big-button phone |
| LW-EMG-PLN-001 | No emergency response plan | SVC-005 Medical Alert System Setup, SMT-006 Wearable Care Alert Kit, EMG-002 First Aid Kit, EMG-003 Emergency Flashlight, EMG-004 Backup Power Light, EMG-005 Medical Information Folder, WEL-010 Elder Care Manager (ECM) Coordination | unchanged | keep |
| LW-HM-ELE-001 | Home electrical concerns | BAL-001 Anti-slip Outdoor Coating, HM-001 Home Electrical Safety Check, HM-003 Home Maintenance Visit, HM-005 Electrician Visit (repair) | HM-001 Home Electrical Safety Check, HM-003 Home Maintenance Visit, HM-005 Electrician Visit (repair) | drop anti-slip outdoor coating |
| LW-HM-PLB-001 | Water leaks or plumbing risk | BAL-002 Safety Railing Upgrade, HM-002 Plumbing Inspection, HM-003 Home Maintenance Visit, HM-004 Plumbing Visit (repair) | SMT-009 Water Leak Sensor, HM-002 Plumbing Inspection, HM-003 Home Maintenance Visit, HM-004 Plumbing Visit (repair) | drop balcony railing; add water leak sensor |
| LW-HM-CLN-001 | Home condition neglected | SVC-004 Deep Home Safety Inspection, HM-003 Home Maintenance Visit, HM-007 Appliance Repair Visit, HM-008 Pest Control, HM-009 Deep Cleaning, HM-010 AC Service | unchanged | keep |
| LW-TECH-LIT-001 | Hard to operate lights | SMT-006 Wearable Care Alert Kit, SMT-011 Room SOS Button | HAL-001 Motion Sensor Light, SMT-008 Voice Assistant | SOS buttons do not fix light switches; voice assistant + motion light |
| LW-TECH-FAL-001 | High fall risk without monitoring | SMT-001 Video Doorbell, SMT-002 Smart Lock, SMT-003 Indoor Camera / CCTV Point, SMT-004 Motion Sensor, SMT-005 Door Sensor, SMT-009 Water Leak Sensor, WEL-014 Smart Home Installation Bundle | SMT-002 Smart Lock, SMT-003 Indoor Camera / CCTV Point, SMT-004 Motion Sensor, SMT-006 Wearable Care Alert Kit, SMT-011 Room SOS Button, WEL-014 Smart Home Installation Bundle | add fall-alert wearable + SOS; drop doorbell, door and water-leak sensors |
| LW-TECH-SEC-001 | Security concerns | SMT-007 Medication Reminder, SMT-008 Voice Assistant, WEL-006 Video Calling Training / Setup, WEL-013 Smartphone Setup | SMT-001 Video Doorbell, SMT-002 Smart Lock, SMT-003 Indoor Camera / CCTV Point, SMT-005 Door Sensor | doorbell/lock/camera/door sensor instead of reminders and phone setup |
| LW-FAM-ECM-001 | Needs care coordination | WEL-006 Video Calling Training / Setup | WEL-010 Elder Care Manager (ECM) Coordination | care coordination is the ECM service, not video-call setup |
| LW-FAM-COM-001 | Family poorly coordinated | WEL-010 Elder Care Manager (ECM) Coordination, TRN-002 Hospital Accompaniment, TRN-003 Airport Assistance | WEL-006 Video Calling Training / Setup, WEL-010 Elder Care Manager (ECM) Coordination | drop airport/hospital transport; add family video calling |
| LW-FAM-LEG-001 | No advance directive or decision-maker | — | unchanged | keep |
| LW-HC-PCP-001 | Missed or fragmented primary care | — | WEL-004 Doctor Visit Assistance, DX-001 Doctor Home Visit, TRN-001 Hospital Drop, TRN-002 Hospital Accompaniment | was unmapped; doctor visit + accompaniment |
| LW-HC-PT-001 | Needs physiotherapy | — | PHY-001 Physiotherapy Initial Assessment, PHY-002 Physiotherapy Home Session, PHY-003 Physiotherapy Monthly Package | was unmapped; physiotherapy |
| LW-FIN-GOV-001 | Possible unused benefits | WEL-010 Elder Care Manager (ECM) Coordination, WEL-012 Benefits & Schemes Counseling | unchanged | keep |
| LW-FIN-DOC-001 | Paperwork barriers | WEL-012 Benefits & Schemes Counseling | unchanged | keep |
| LW-WELL-AGE-001 | Lifestyle risk factors | WEL-002 Companion Visit | unchanged | keep |
| LW-WELL-SOC-001 | Low engagement | — | WEL-002 Companion Visit | was unmapped; companion visits |
| LW-PM-INSP-001 | Unsupervised property risk | PM-001 Monthly Home / Property Inspection, PM-002 Utility Bill Assistance, PM-003 Contractor Supervision, PM-004 Renovation Supervision | unchanged | keep |
