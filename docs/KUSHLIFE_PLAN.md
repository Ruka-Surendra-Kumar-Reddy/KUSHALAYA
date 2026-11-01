# KushLife — plan for the family portal

**Owner:** Krish Posa · **Drafted:** 2026-09-29 · **Status:** proposal (marketing part is built; portal part is not started)

## What KushLife is

KushLife is the family-facing name for everything that happens *after* the
Kushalaya Assessment (KAA): the visits, the check-ins, the trend. The line is
**"Every visit, we assess the 'kush'-ness."** — "kush" being the everyday word
for comfort, ease and contentment.

The assessment answers "is the home safe?" once. KushLife answers "how is my
parent actually living?" every visit. That is the selling point: a family sees
a trend, not just an incident.

## The good news: the data already exists

Every visit already records a structured **check-in**
(`backend/app/livewell/care_stability.py`, `empty_checkin()`): overall status,
mood, mobility, eating, medication, new symptoms, home-safety issue, fall since
last visit, unsteadiness, fear of falling, and a family message. From it the
backend computes a **stability score (0–100)** with a per-visit history and a
delta, and publishes a **wellness report** to the family portal.

The family portal already shows all of this, but under engineering names:
"Care stability trend", "Wellness reports", "Care status". KushLife is mostly a
**naming and framing job on top of what is built**, plus one small schema
addition so the four public checks line up with the data.

## The four KushLife checks and where they come from

| Check | Public promise | Existing check-in fields |
|---|---|---|
| **Safe** | hazards, lighting, grab bars, footwear | `home_safety_issue`, `home_safety_note` |
| **Steady** | walking, balance, confidence | `mobility`, `mobility_vs_normal`, `fallen_since_last`, `unsteady`, `worried_about_falling` |
| **Settled** | sleep, meals, medicines, mood, routine | `mood`, `mood_vs_normal`, `eating`, `eating_vs_normal`, `medication`, `new_symptoms` |
| **Connected** | what they want the family to know; what the family asked | `family_message`, `new_request`, `request_note`, `follow_up_required` |

Nothing new has to be asked in the field for phase 1. Sleep is the one item
promised on the site that is not captured today (see phase 2).

## Phases

### Phase 1 — Naming (frontend only, ~1 day)

Rename what the family sees. No backend change, no migration.

- Family dashboard (`app/kushalaya/family/(portal)/dashboard/page.tsx`):
  "Care stability trend" → **"KushLife trend"**; the score tile label
  "Independence" stays (that is the KAA score) and the stability tile becomes
  **"KushLife score"** with the same "↑ 4 since last visit" delta.
- `components/livewell/family/StabilityScoreChart.tsx`: heading and aria label.
- Wellness page (`(portal)/wellness/page.tsx`): title **"KushLife visits"**,
  subtitle "What we checked on each visit". Each report card gets a
  four-chip row — Safe / Steady / Settled / Connected — derived on the client
  from the highlights until phase 2 returns them explicitly.
- Nav label in the shared package (`workforceos-core/contracts/nav.json` +
  `shell/nav.ts` + `typescript/dist/shell/nav.js`, all three together):
  "Wellness" → "KushLife". This is the one change that touches the shared
  package, so it deploys separately (see CLAUDE.md, *Shared platform changes*).
- Family login page strapline: "Your family's KushLife, in one place."
- Digest emails/WhatsApp briefs (`backend/app/livewell/family_care_hub.py`):
  subject line "KushLife update — <name>" — copy only.

Acceptance: a signed-in family member sees the word KushLife on the dashboard,
the visits page and the nav, and nothing else moved.

### Phase 2 — Four explicit checks per visit (backend + ops form, ~3 days)

Make the four checks first-class so the site's promise is literally true.

- Backend: extend `normalize_checkin()` with an optional `kush` block
  `{safe, steady, settled, connected}` each `"good" | "watch" | "concern"`,
  and `sleep` (`normal | poor | much_worse`). Derive the four ratings from
  the existing fields when the block is absent, so old visits still render.
- `publish_wellness_from_visit()` puts `kush_checks` on the wellness report;
  `WellnessReportResponse` and the frontend `WellnessReport` type gain the
  field; the client-side derivation from phase 1 is deleted.
- Ops visit form (assessor app, `components/livewell/…` check-in UI): a
  four-tile "KushLife check" row at the top of the check-in, one tap each,
  required before a visit can be closed. ~30 seconds per visit.
- Stability score: fold `sleep` into the existing weights so the number
  reflects what is now asked.
- Tests: `backend/tests` for derivation + normalisation; frontend test for
  the chip row.

### Phase 3 — Trend, alerts and the monthly letter (~1 week)

- Dashboard: the KushLife trend chart gets the four checks as a stacked
  strip under the line, so a family sees *which* dimension dipped.
- Alert rule (`rule_engine_defaults.py`): two consecutive "concern" ratings
  on any check, or a score drop of ≥ 15, raises a family alert — the
  existing alert channel, new reason text.
- Monthly **KushLife letter**: one page per elder, generated from the visit
  history (score line, four-check summary, care manager's note, photos).
  Delivered in the portal under Documents and as the WhatsApp brief.
  Reuse the assessment report generator (`lib/livewell/assessment-report.ts`)
  layout.

### Phase 4 — Packaging (commercial, no code beyond copy)

- Packages page: every ongoing plan lists **"KushLife visits: N per month"**
  as the first line item, above the modifications.
- Brochure and vision sheet: replace "Ongoing support" bullets with the
  KushLife line.
- Optional later: a KushLife badge (score band) in the family-portal header,
  and a printable fridge card for the elder with the next visit date.

## What is already live from this plan

- www.kushalaya.com: KushLife band (`#kushlife`) after *How it works*, a
  trust badge and a *What you receive* card, nav + footer links, and the
  founder section (`#founder`) with direct phone and email.
- Vision sheet (`/vision`): *From the founder* block with the same contact.
- Source of truth for the copy: `frontend/lib/marketing/founder.ts`
  (`FOUNDER`, `KUSHLIFE`).

## Decisions needed from the owner

1. Spelling in product UI: **KushLife** (one word, capital L) is what the
   site uses. Confirm before it goes into the portal nav and emails.
2. Whether the KAA "Independence Score" keeps its name or becomes the
   "KushLife baseline". Recommendation: keep it — one is the home, the other
   is the person, and families understand two numbers with two names.
3. Phase 2 adds one question (sleep) to every visit. Confirm the field team
   is fine with that.
