# Care observation protocol

Staff script for LiveWell wellness visits. Care coordination only — **not a medical diagnosis** and **not a certified WHO/CDC/AARP instrument**.

Inspired by:

- **WHO ICOPE** — domain map for community workers (locomotion, vitality/nutrition, psychological, light cognition, continence on baseline)
- **CDC STEADI** — fall cues (fallen / unsteady / worried), medications, light home hazards
- **AARP HomeFit** — framing for a home glance only (full home score remains KAA)

## Message for family

Caregivers enter **Message for family** on baseline and check-in visits. That text is shown on:

- Family dashboard care status card (“Message from Care Manager”)
- Visit report detail
- Wellness reports timeline

It is separate from optional internal visit summary teasers.

| Visit | Score |
|-------|-------|
| First **Baseline profile** visit | **50** — personal normal (room to improve or decline) |
| Later check-ins | 0–100 from multiple-choice fields; **better** vs normal raises above 50; **worse** lowers |

Bands (approx.): ≥65 improved · 45–64 stable · 30–44 declining · &lt;30 critical.

Hard flags (fall / emergency) cap the score low. History is stored on `safe_home.stability_score_history` and shown on the family portal as **Care stability trend** (not the Independence Score™ assessment card).

See also: [CARE_STABILITY.md](./CARE_STABILITY.md) for end-to-end product behavior.

## Baseline visit (first completed visit)

Ordered steps — each has **Look for**, **Ask**, **Record** (dropdowns preferred):

1. Arrive & context  
2. Contact / alertness  
3. Mobility & falls (STEADI cues + mobility/fall history dropdowns)  
4. Daily rhythm (wake, sleep, leave-home band)  
5. Eating & bathroom (appetite band)  
6. Medications  
7. Home glance  
8. **Close** — record Yes / Partially / No for “normal day?”, optional close notes; score = 50

## Recurring check-in (60–90s)

1. Contact outcome  
2. Mood + vs normal  
3. Mobility & STEADI fall questions + vs normal  
4. Eating + vs normal  
5. Meds / symptoms / home / requests  
6. Overall judgment + note  

## Product files

- Protocol data: `frontend/lib/livewell/care-observation-protocol.ts`  
- Score engine: `backend/app/livewell/care_stability.py` → `compute_stability_score`  
- Staff UI: `frontend/app/(app)/livewell/visits/page.tsx`  
