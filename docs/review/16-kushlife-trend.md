# KushLife trend design

## Today: two visit models that never meet

**New 4-check model**
- Stored in `CareJob.report.checks` (`visit_reports.py:152`).
- No family page reads it. Families only get a one-line notification. Ops sees it as text in `ClientHistory.tsx:85`.
- No history and no flags.

**Old check-in model**
- Stability score: 50 means "personal normal" (`care_stability.py`, history in `custom_attributes`).
- Care status RED/YELLOW/GREEN.

**Contradiction**
- The family dashboard labels the OLD stability number "KushLife" and "KushLife pulse" (`dashboard:168,271`).
- New 4-check visits never move it, so families can see a stale number while getting "Needs attention: Steady" messages.
- The dashboard bands (55/50/45) disagree with the backend's (65/45/30).
- "Steady" is both a band name and a check name.

## Trend design

**Family card: "KushLife — last 8 visits"**
- 4 rows × 8 dots, green or amber, with dates.
- One line under it, e.g. "Steady: 2 concerns in last 3 visits — Asha is reviewing" or "All four fine for 6 visits in a row".
- No number. Optional "94% of checks fine in 30 days".

**Care manager view**
- 12-visit grid, notes on hover, streaks.
- Open flags with Acknowledge / Resolve.
- A "Needs review" queue.

**Thresholds**
- **Amber:** any Safe concern, or 2 concerns on the same check in the last 3 visits.
- **Family told:** after the manager acknowledges, or after 24 hours.
- **Red:** 3 in a row, a fall, or 3 or more checks in concern on one visit. Means a same-day call and a suggested reassessment.

**Chips when a check is a concern**
- Steady: fall / unsteady / fear of falling
- Settled: poor sleep / ate less / low mood / missed meds
- Connected: lonely / message for family
- Optional BP and SpO₂, plus photos

**Link to the Independence Score:** a red flag, or 40% or more concerns in 30 days → "Suggest reassessment".

## One score story

- **Independence Score™** = measured at the assessment.
- **KushLife** = checked every visit.
- Remove the 0–100 stability/pulse number and "personal normal = 50" from family views.
- Merge care status into KushLife:
  - "All good"
  - "Keeping an eye on it"
  - "We've called you"

Family copy: "Every visit, the caregiver checks four things — Safe, Steady, Settled, Connected. Green means as usual; amber means something changed and your care manager is looking at it."

## Data and API

**Changes**
- Report gains `tags`, `vitals` and `checks_version`.
- Read-time adapter maps old check-ins to the 4 checks.
- New table `kushlife_flags` (needs `--backend-migrate`).
- `GET family/kushlife?limit=8` and staff `elders/{id}/kushlife?limit=12` return visits, streaks, `pct_ok_30d`, open flags and the summary line.
- `POST flags/{id}/ack` and `POST flags/{id}/resolve`.

**Effort**

| Piece | Size |
|---|---|
| Unify the two models | M |
| Family grid | S–M |
| Flags, rules and queue | M |
| Chips | S |
| Reassessment hook | S |
| Retire the stability UI | S |
| **Total** | **about L (1.5–2 weeks)** |
