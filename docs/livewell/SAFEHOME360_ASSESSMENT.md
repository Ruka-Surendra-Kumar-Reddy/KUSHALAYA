# SafeHome 360™ — Assessment Framework

**Framework version:** 1.0  
**Product name:** SafeHome 360™  
**Assessment duration:** 45–90 minutes (field)  
**Platform:** Mobile assessor PWA (`/home-safety`)

This document describes how the on-site home safety assessment works in **SafeHomeOps**: structure, scoring, wizard flow, data model, and integration points.

---

## Overview

SafeHome 360™ is a standardized senior home safety assessment that produces:

| Output | Description |
|--------|-------------|
| **SafeHome Score™** | Normalized **0–100** score |
| **Safety grade** | Platinum / Gold / Silver / Bronze / Red |
| **Risk level** | Low / Moderate / High / Immediate action |
| **Safety Age™** | Illustrative “safety age” vs resident age |
| **Room-by-room scores** | Per-section point totals |
| **Care pathway** | Membership + ECM indication (score + family + cognitive flags) |
| **Findings** | Observed unsafe/acceptable items with notes |
| **Improvement plan** | Library v1 solutions (`LW-CAT-SUB-nnn`) with Evidence A/B/C + projected score |
| **Customer quote** | Product SKUs + priced estimate (margin, labor, GST) |
| **Family report** | Structured text report (`formatAssessmentReport`) — copy / share / pipeline |

Solution → product → pricing detail: [SOLUTION_CATALOG_PRICING.md](./SOLUTION_CATALOG_PRICING.md).

**AI role:** Room before/after visuals for **approved** solutions only. Optional narrative polish may rephrase `buildReportNarrativeBrief` facts — AI must not invent solutions, products, or diagnoses. Recommendations stay rule/catalog-driven.

**Not yet automated:** PDF family report, supplier/installer selection, quote approval workflow (see [roadmap](#planned-enhancements)).

---

## User-facing apps

**Production host:** `https://ops.kushalaya.com` — full URL table: [README.md § Apps & URLs](./README.md#apps--urls).

| App | URL | Role |
|-----|-----|------|
| Assessor PWA | `/home-safety` | Field assessors |
| Assessment form | `/home-safety/assess/{id}` | Step-by-step wizard |
| Family login | `/home-safety/family/login` | Family portal role |
| Family PWA | `/home-safety/family` | Children & family |
| Showcase | `/home-safety/showcase` | Product presentation |
| Admin rubric | `/home-safety/rubric` | Tenant checklist editor |
| Admin solutions | `/home-safety/solutions` | Solution library (`SH-*`) |
| Admin catalog | `/home-safety/catalog` | Products, packages, solution links |
| Admin pricing | `/home-safety/pricing` | Margin, labor, travel, GST |
| Admin suppliers | `/home-safety/suppliers` | Vendor directory |
| Admin master data | `/home-safety/master-data` | Excel import / export / seed |
| Admin visits | `/home-safety/visits` | Log Safe Home visits |

Admin sidebar: **Safe Home 360™** group, or **Settings → Home safety assessments**.

---

## Assessment wizard (assessor UX)

The assessment is **not** one long scroll. It uses a **step-by-step wizard**:

| Step | Content |
|------|---------|
| 1 | **Resident profile** (Section 1 — not scored) |
| 2–N | **One scored section per step** (Exterior, Bathroom, …) |
| N+1 | **Before photos** |
| Last | **Review & save** — score, improvement plan, customer quote, recommendations, finalize |

**Navigation**

- Dot progress bar at bottom — jump to any step  
- **Back / Next** — Next warns if current section is incomplete  
- Top bar shows **% checklist complete** while scoring  
- Profile step shows how many questions are **hidden** by conditional logic  

**Draft behavior**

- Auto-saves to browser `localStorage` every ~2 seconds  
- **Save assessment** (review step) requires 100% of *applicable* items rated + resident first name  
- When signed in to WorkforceOS, save also creates/updates a **prospect** in the pipeline  

---

## Section structure

### Section 1 — Resident profile (no score)

Collected on the intake step. Drives **conditional show/hide** for later sections (see [CONDITIONAL_LOGIC.md](./CONDITIONAL_LOGIC.md)).

Includes: resident name, age, address, dwelling type, living situation, mobility device, medical conditions, family contacts, assessor, pain points.

### Scored sections (2–13)

| § | Section | Raw points | Category id |
|---|---------|------------|-------------|
| 2 | Exterior & Entry | 10 | `exterior` |
| 3 | Living Room | 10 | `living_room` |
| 4 | Bathroom | 25 | `bathroom` |
| 5 | Bedroom | 15 | `bedroom` |
| 6 | Kitchen | 10 | `kitchen` |
| 7 | Hallways | 10 | `hallways` |
| 8 | Balcony | 5 | `balcony` |
| 9 | Mobility Assessment | 20 | `mobility` |
| 10 | Emergency Preparedness | 10 | `emergency` |
| 11 | Smart Home Readiness | 10 | `smart_home` |
| 12 | Wellness Observation | 15 | `wellness` |
| 13 | Family Support Assessment | 10 | `family_support` |

**Total raw weight:** 150 points (distributed across all checklist items in each section).

Source of truth: `frontend/lib/livewell/safehome360-rubric.ts`

---

## Rating scale (per question)

Assessors tap one of four options on each item:

| UI label | Meaning | Standard scale (2/1/0) | Critical scale (4/2/0) |
|----------|---------|------------------------|-------------------------|
| **Excellent** ★ | Fully compliant | 100% of item weight | 100% |
| **Acceptable** ~ | Minor improvement needed | 50% | 50% |
| **Unsafe** ✕ | Immediate improvement required | 0% | 0% |
| **N/A** — | Not applicable | Excluded from denominator | Excluded |

**Critical items** (e.g. grab bars, anti-slip) are tagged in the rubric and use the 4/2/0 weighting internally; the same four buttons are shown.

**Legacy ratings** (`pass` / `partial` / `fail` from older assessments) are normalized automatically to Excellent / Acceptable / Unsafe.

**Item notes** — optional text when rating is Acceptable or Unsafe (findings for reports).

---

## Scoring methodology

### Per-item points

```
excellent  → 100% × item.maxPoints
acceptable →  50% × item.maxPoints
unsafe     →   0% × item.maxPoints
na         → excluded from earned and max totals
unrated    →   0% earned, still counts in max until rated
```

### SafeHome Score™ (0–100)

Only **applicable** items count (after conditional logic):

```
score = round( (sum of earned points) / (sum of applicable item weights) × 100 )
```

Implemented in `normalizedScore()` — `frontend/lib/livewell/assessment.ts`

### Safety grade

| Score | Grade |
|-------|-------|
| 95–100 | Platinum |
| 85–94 | Gold |
| 75–84 | Silver |
| 65–74 | Bronze |
| Below 65 | Red |

### Risk level

| Score | Risk |
|-------|------|
| ≥ 85 | Low Risk |
| 75–84 | Moderate Risk |
| 65–74 | High Risk |
| &lt; 65 | Immediate Action Required |

### Safety Age™

Illustrative model aligned with spec examples:

```
safetyAge = residentAge + round((100 - score) × 0.43)
projectedAfterImprovements = safetyAge(residentAge, min(100, score + 15))
```

Requires resident age on the profile step.

---

## Review step: improvement plan & quote

On the final wizard step (before save), the assessor sees:

| Panel | Source | Purpose |
|-------|--------|---------|
| **Score summary** | `assessment.ts` | SafeHome Score™, grade, Safety Age™ |
| **Improvement plan** | `improvement-plan.ts` | Solutions matched from Unsafe/Acceptable ratings |
| **Customer quote** | `product-recommendations.ts` + `pricing-engine.ts` | SKUs, cost breakdown, grand total |
| **Assessor notes** | Free text | Additional recommendations |

**Improvement plan** triggers when checklist items are rated **Unsafe** or **Acceptable**. Solutions are matched via `rubricItemIds` on each `SH-*` entry.

**Customer quote** resolves catalog products where `solution_ids` includes the matched solution. Pricing uses tenant config from `/home-safety/pricing` (margin, labor rate, travel, GST, etc.). Assessor can adjust travel km, labor hours, and weekend/emergency surcharges before save.

The text report (copy / share / prospect sync) includes improvement plan, product lines, and quote estimate when catalog and pricing are loaded.

See [SOLUTION_CATALOG_PRICING.md](./SOLUTION_CATALOG_PRICING.md).

---

## Data model

### Assessment record (`HomeSafetyAssessment`)

Stored in browser: `localStorage` key `safehome_home_safety_assessments_v1` (legacy: `eldercare_home_safety_assessments_v1`)

| Field | Purpose |
|-------|---------|
| `clientFirstName` / `clientLastName` | Resident name |
| `clientAddress`, `clientPhone`, `clientEmail` | Contact |
| `familyContactName` / `familyContactPhone` | Pipeline & family |
| `residentProfile` | Section 1 intake + conditional flags |
| `ratings` | `itemId → excellent \| acceptable \| unsafe \| na` |
| `itemNotes` | Per-item observations |
| `photos` | Before photos (local + uploaded `documentId`) |
| `notes` | Assessor recommendations (free text) |
| `painPoints` | Visit notes |
| `frameworkVersion` | e.g. `1.0` |
| `prospectId` / `elderId` | After pipeline sync |

### Rubric storage

| Store | Key / path | Notes |
|-------|------------|-------|
| Default rubric | `safehome360-rubric.ts` | Shipped with app |
| Tenant override | `localStorage` `safehome_home_safety_rubric_v2` (legacy: `eldercare_*`) | Admin editor |
| Backend mirror | `backend/app/livewell/rubric.py` | API / family defaults (legacy 7-category; frontend is authoritative for assessor) |

---

## Code map (developers)

| Concern | File(s) |
|---------|---------|
| Rubric data (sections & items) | `frontend/lib/livewell/safehome360-rubric.ts` |
| Scoring & grades | `frontend/lib/livewell/assessment.ts` |
| Conditional rules | `frontend/lib/livewell/conditional-rules.ts`, `conditional.ts` |
| Resident profile types | `frontend/lib/livewell/resident-profile.ts` |
| Wizard steps | `frontend/lib/livewell/assessFlow.ts` |
| Assessment UI | `frontend/app/home-safety/(portal)/assess/[id]/page.tsx` |
| Intake form | `frontend/components/livewell/AssessmentIntakeForm.tsx` |
| Section panel | `frontend/components/livewell/AssessmentSectionPanel.tsx` |
| Rating control | `frontend/components/livewell/RatingControl.tsx` |
| Local persistence | `frontend/lib/livewell/storage.ts` |
| Prospect sync | `frontend/lib/livewell/syncProspect.ts` |
| Improvement plan | `frontend/lib/livewell/improvement-plan.ts`, `ImprovementPlanPanel.tsx` |
| Product quote | `frontend/lib/livewell/product-recommendations.ts`, `pricing-engine.ts`, `ProductQuoteDraftPanel.tsx` |
| Unit tests | `assessment.test.ts`, `conditional.test.ts`, `improvement-plan.test.ts`, `pricing-engine.test.ts` |

---

## Pipeline & family integration

**On save (signed-in assessor)**

1. Assessment marked `completed` in localStorage  
2. `syncAssessmentToProspect()` → prospect with stage `ASSESSMENT_DONE`, care level from grade  
3. Full text report appended as prospect activity (includes improvement plan + quote when configured)  
4. Photos uploaded to `POST /api/v1/home-safety/photos` when possible  

**Family app**

- Reads `elder.custom_attributes.safe_home` for score, wellness, visits  
- Does **not** yet read live assessor localStorage assessments  
- To show a completed assessment to family: write `safe_home.safety_score` on the elder record (manual or future API sync)  

---

## Admin: customizing the checklist

1. Open `/home-safety/rubric` (or Settings link)  
2. Add/edit categories and items; set point weights  
3. **Reset to defaults** restores SafeHome 360™ v1.0 rubric  
4. Conditional `skipWhen` rules on custom items are not editable in UI yet — they are defined in `safehome360-rubric.ts` for default items  

---

## Planned enhancements

| Feature | Status |
|---------|--------|
| SafeHome 360 wizard & scoring | Shipped |
| Conditional show/hide | Shipped — [CONDITIONAL_LOGIC.md](./CONDITIONAL_LOGIC.md) |
| Solution library → improvement plan | Shipped |
| Product catalog + solution links | Shipped — [SOLUTION_CATALOG_PRICING.md](./SOLUTION_CATALOG_PRICING.md) |
| Pricing engine + customer quote | Shipped |
| Supplier / installer masters | Planned |
| Quote approval & work orders | Planned |
| Server-side assessment persistence | Planned |
| PDF family report | Planned |
| Family-visible live quote | Planned |

---

## Related docs

- [README.md](./README.md) — vertical overview, URLs, catalog, visits  
- [SOLUTION_CATALOG_PRICING.md](./SOLUTION_CATALOG_PRICING.md) — solutions, catalog, pricing, quotes  
- [CONDITIONAL_LOGIC.md](./CONDITIONAL_LOGIC.md) — profile-driven question filtering  
