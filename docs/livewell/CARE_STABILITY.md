# Care stability & family portal

Care coordination for enrolled clients (after conversion). **Not a medical diagnosis.**

## Two scores (do not confuse them)

| Score | Source | Family UI | Cadence |
|-------|--------|-----------|---------|
| **Independence Score™** | One-time (or rare) KAA home assessment publish | Single number / grade on dashboard & Safety page — **no trend graph** | Intake |
| **Care stability score** | Structured Care Manager visits | Care status card + **Care stability trend** chart | Every completed visit |

After someone becomes a customer, ongoing trend comes from **visits**, not repeated full assessments.

## Baseline visit (first completed visit)

1. Staff uses Observe / Ask protocol on `/livewell/visits` (WHO ICOPE domains + CDC STEADI fall cues; AARP HomeFit framing for home glance only).
2. Most fields are **dropdowns** (mobility, communication, wake/sleep, appetite, meds, home hazards, Close confirmation, etc.).
3. Visit type forced to **Baseline profile**.
4. **Stability score = 50** (personal normal). Room to rise or fall later.
5. Optional **Message for family** is shown on the family dashboard and visit report.
6. Baseline is stored on `elder.custom_attributes.safe_home.care_baseline`.

## Later visits (check-in)

1. Same page shows structured check-in steps (all multiple-choice for scoring).
2. Key scoring fields: overall, mood/mobility/eating (+ vs-normal better/same/worse), STEADI fallen/unsteady/worried, meds, contact outcome, flags.
3. `compute_stability_score()` starts at 50 and applies deltas from those enums.
4. Mom-is-OK status: GREEN / YELLOW / RED (`ok` / `needs_attention` / `urgent`) from the same check-in + open incidents/requests.
5. Score + meta saved on the visit and appended to `safe_home.stability_score_history`.

## Family portal

- **Care status** card: headline, snapshot domains, family message, latest **stability score**.
- **Care stability trend**: sparkline from `stability_score_history` (backfills from visits if history list empty). Dashed line at 50 = personal normal.
- Independence Score™ card remains as the assessment snapshot (no assessment history chart).

## Key code

| Area | Path |
|------|------|
| Score + status engine | `backend/app/livewell/care_stability.py` |
| Visit create / history | `backend/app/livewell/visit_service.py` |
| Family dashboard payload | `backend/app/livewell/family_service.py` |
| Staff protocol + form | `frontend/lib/livewell/care-observation-protocol.ts`, `frontend/app/(app)/livewell/visits/page.tsx` |
| Family UI | `FamilyCareStatusCard`, `StabilityScoreChart`, family dashboard |
| Field guide | `docs/livewell/CARE_OBSERVATION_PROTOCOL.md` |

## APIs

- Staff: `POST /api/v1/home-safety/visits` (baseline or check-in), baseline GET/PUT
- Family: `GET /api/v1/home-safety/family/dashboard` → `care_status`, `stability_score_history`, `stability_score_delta`, `latest_stability_score`

## Tests

- `backend/tests/test_care_stability.py` — status rules + score math (50 center, improve, decline, fall)
- `backend/tests/test_home_safety_visits.py` — first visit requires baseline, score 50, family message, history on dashboard

## Ops navigation

Staff find visits under **Care delivery → Visits & check-ins**. Full sidebar + role matrix: [OPS_PORTAL_NAV.md](./OPS_PORTAL_NAV.md).
