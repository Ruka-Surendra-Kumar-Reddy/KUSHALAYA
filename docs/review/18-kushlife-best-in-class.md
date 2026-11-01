# KushLife best-in-class design

## Starting point
- Today a visit saves only 4 ok/concern flags plus a note (`visit_reports.py:143`).
- A richer check-in already exists in `care_stability.empty_checkin()`: mood, eating, mobility, falls, fear of falling, medicines.
- **Merge the two into one KushLife record.** Don't add a third.
- **Benchmarks:**
  - RESTORE2 / RESTORE2mini: UK soft signs of deterioration, usable without vitals.
  - Stop and Watch: a checklist for carers and families.
  - Birdie and Cera log observations on each visit.
  - KushLife can beat all of these on the family side.

## Capture: 3 minutes or less, about 40 seconds when nothing has changed
Each check starts on "Same as usual ✓". Tapping "Changed" opens chips.

| Check | What changes can be recorded |
|---|---|
| **Safe** | new hazard (uses the existing `add_hazard`), medicines taken / missed / unsure, stove/gas, doors, lighting, footwear, photo |
| **Steady** | fall, near-fall, unsteady, fear of falling; walking aid and whether it was used; optional 30-second stand-and-walk timer (Timed Up and Go, TUG) |
| **Settled** | appetite and fluids, sleep, mood, new confusion, pain 0–10, continence, skin, breathing |
| **Connected** | visitors and calls (chips); a 3-item loneliness check (UCLA) once a month; "message for family" |

Also on every visit:
- **Vitals (optional, folded away):** BP, sugar, SpO2, temperature; weight monthly.
- **Voice note** in Telugu, Hindi or English → transcript → draft note.
- **"Flag for manager":** urgent or today.

## Rules: decision support, not diagnosis

| Trigger | What happens |
|---|---|
| New fall, 2 or more new soft signs, SpO2 below 92, or temperature 38 °C or more | Urgent task for the manager (2-hour target) and a family message, e.g. "Ravi noticed Amma seemed more confused than usual and is arranging a doctor check today." |
| Same check is a concern on 2 visits in a row | Manager task within 24 hours and a suggested reassessment |
| Appetite down for 3 visits, or weight down more than 5% | Nutrition review or GP visit |
| Pain at least 3 points above her baseline | Doctor review |
| High loneliness | Companionship visit or family call |

- **Personal baseline:** the median of her last 6–8 visits for each field. Shown as, e.g., "Walking: usual for her (stick)".
- **Weekly AI summary:** approved by the manager before it reaches the family. Never uses disease words.

## Family experience
- **Every visit:** a card with 4 coloured checks, each compared with her usual, plus a photo, Amma's message and what the team did.
- **Every week:** a summary, a dot strip, open flags shown as raised → acting → resolved, and the next visit.
- **Ways to respond:**
  - "Call me": creates a manager task in the family member's timezone.
  - "Ask about…": goes into the next visit's Connected step.
  - A heart.
- **Siblings:** each sets their own level (every visit / weekly / flags only), language and timezone, and sees who has already responded.

## Operations
- Checklist for each client built from the care plan, e.g. diabetes adds a sugar reading; a past fall makes TUG required.
- Missed KushLife raises an alert, or a visit can't be closed without it.
- **Metrics:**
  - completion %
  - capture time
  - flags per 100 visits
  - time to acknowledge and to resolve
  - precision (flags that led to real action)
  - hospital admissions with no flag beforehand
  - family open rate and NPS

## Build plan

**MVP: medium, about 1.5 weeks, no migration**
- `report.kushlife` with version, checks (status, chips, note), vitals, pain, flag and duration.
- Mapped onto the stability check-in, so the existing trend keeps working.
- "Same as usual" capture with chips.
- Rules: fall, 2 in a row, missed KushLife.
- Family card for each visit.

**v2: large, about 3 weeks, `--backend-migrate`**
- `kushlife_baselines` and `kushlife_flags` tables, plus the flags API.
- Weekly AI summary with a manager approval queue.
- "Call me" and "Ask about…".
- Per-sibling preferences.
- Checklist built from the care plan.

**v3: large**
- Voice transcription.
- Vitals trends, including Bluetooth devices and the IoT link.
- Monthly UCLA loneliness check and TUG test.
- Monthly letter PDF.
- Quality dashboard.

## Proof it works
| Measure | Target |
|---|---|
| Capture time (90% of visits) | under 3 minutes |
| Completion | over 95% |
| Urgent flags acknowledged within 2 hours | over 90% |
| Flags that lead to an action | at least 1 in 3 |
| Unplanned hospital visits | fewer than before |
| Family open rate | over 70% |

## Owner decisions
- Manager approves AI summaries before families see them (recommended).
- Block closing a visit without KushLife?
- Which vitals kit do managers carry?
