# SafeHome 360™ — Conditional Logic

The assessor does **not** answer every question on every visit. Section 1 (resident profile) drives which checklist items and sections appear, reducing a full ~150-item rubric to typically **60–90 questions** depending on the home and resident.

---

## How it works

```
Resident profile (Section 1)
        ↓
evaluateConditionalRule() / field matches on SkipRule
        ↓
getApplicableCategories() filters sections & items
        ↓
Wizard shows only applicable steps
        ↓
Scoring & completion % use only applicable items
```

**Implementation**

| Layer | File |
|-------|------|
| Rule definitions | `frontend/lib/livewell/conditional-rules.ts` |
| Filter engine | `frontend/lib/livewell/conditional.ts` |
| Per-item rules on rubric | `frontend/lib/livewell/safehome360-rubric.ts` |
| Profile fields | `frontend/lib/livewell/resident-profile.ts` |

**SkipRule shape** (`assessment.ts`)

```ts
{ when: "unless_has_stairs" }           // named rule
{ field: "smartHomeAssessment", equals: false }  // direct profile field
```

When a rule **matches**, the item or section is **hidden**.

---

## Profile fields that control logic

| Field | Type | UI (intake step) | Effect |
|-------|------|------------------|--------|
| `hasStairs` | boolean | Has stairs | Staircase / ramp / handrail items |
| `mobilityDevice` | `none` \| `cane` \| `walker` \| `wheelchair` | Mobility device dropdown | Wheelchair-only accessibility items |
| `livesAlone` | boolean | Lives alone | Solo-living monitoring items |
| `hasBalcony` | boolean | Has balcony / terrace | Entire Section 8 |
| `smartHomeAssessment` | boolean | Include smart-home section | Entire Section 11 |
| `smartHomeAdvanced` | boolean | Include advanced smart devices | Advanced smart-home items only |
| `domesticHelper` | boolean | Domestic helper | “Domestic helper verified” |
| `fullTimeCaregiver` | boolean | Full-time caregiver | Reserved for future rules |

Other profile fields (age, medical conditions, children location, etc.) are stored for the report and future rules but **do not** hide items in v1.0.

---

## Named rules reference

| Rule id | `RULE` constant | Hidden when… |
|---------|-----------------|--------------|
| `unless_has_stairs` | `STAIRS` | `hasStairs` is not checked |
| `unless_wheelchair_user` | `WHEELCHAIR` | `mobilityDevice !== "wheelchair"` |
| `unless_lives_alone` | `LIVES_ALONE` | `livesAlone` is not checked |
| `unless_smart_home_advanced` | `SMART_ADVANCED` | `smartHomeAdvanced` is not checked |
| `unless_has_balcony` | `BALCONY` | `hasBalcony` is not checked |
| `unless_domestic_helper` | `DOMESTIC_HELPER` | `domesticHelper` is not checked |
| `unless_full_time_caregiver` | `FULL_TIME_CAREGIVER` | `fullTimeCaregiver` is not checked |
| `unless_assistive_device` | `ASSISTIVE_DEVICE` | No cane / walker / wheelchair selected |
| `unless_ramp_relevant` | `RAMP` | No stairs **and** not wheelchair user |

**Field rule**

| Rule | Hidden when… |
|------|--------------|
| `smartHomeAssessment === false` | Entire **Smart Home Readiness** section |

---

## Spec examples → implementation

| SafeHome 360 spec example | Implementation |
|---------------------------|----------------|
| Apartment, no stairs → skip staircase questions | `STAIRS` on handrails, thresholds, climb one step, entrance railing; `RAMP` on ramp items |
| Not wheelchair user → skip wheelchair accessibility | `WHEELCHAIR` on door width, shower chair, transfer rails, counter height, etc. |
| Not living alone → skip solo-living monitoring | `LIVES_ALONE` on emergency buttons, phone nearby, neighbor support, emergency key |
| No smart devices → hide advanced smart-home | Section off via `smartHomeAssessment`; basic items (internet, SOS, smoke) remain unless section off entirely. Advanced items need `smartHomeAdvanced` |

---

## Items affected by rule (default rubric)

### `STAIRS` — hidden when no stairs

| Section | Items |
|---------|-------|
| Exterior | Entrance railing |
| Hallways | Handrails, Safe thresholds |
| Mobility | Climb one step |

### `RAMP` — hidden when no stairs and not wheelchair

| Section | Items |
|---------|-------|
| Exterior | Ramp required, Ramp installed |

### `WHEELCHAIR` — hidden when not wheelchair user

| Section | Items |
|---------|-------|
| Exterior | Door width adequate |
| Bathroom | Toilet support rails, Transfer space adequate, Shower chair, Foldable grab bar, Sink height appropriate |
| Bedroom | Closet accessibility |
| Kitchen | Counter height appropriate, No climbing required |
| Hallways | Door width |

### `LIVES_ALONE` — hidden when not living alone

| Section | Items |
|---------|-------|
| Living room | Phone accessible, Emergency button |
| Bedroom | Phone nearby, Emergency button |
| Bathroom | Door unlockable externally |
| Emergency | Neighbor support, Emergency key |
| Family support | Neighbor support |

### `ASSISTIVE_DEVICE` — hidden when mobility device is none/empty

| Section | Items |
|---------|-------|
| Mobility | Uses assistive device correctly |

### `BALCONY` — hidden when no balcony

Entire **Section 8 — Balcony** (all items).

### `NO_SMART_HOME` — section hidden

Entire **Section 11 — Smart Home Readiness** when “Include smart-home section” is unchecked.

### `SMART_ADVANCED` — hidden when advanced not selected

| Section | Items shown only with advanced checked |
|---------|----------------------------------------|
| Smart home | Smart doorbell, Smart lock, Motion sensors, Indoor camera, Water leak sensor, Medication reminder, Voice assistant |

**Always shown** when smart-home section is on: Internet available, SOS button, Smoke detector.

### `DOMESTIC_HELPER` — hidden when no helper

| Section | Items |
|---------|-------|
| Family support | Domestic helper verified |

---

## UX feedback

On the **Resident profile** step, the app displays:

> Based on this profile, **N** questions are hidden (**M** will be asked).

Counts come from `countSkippedItems()` and `getApplicableItems().length`.

When profile answers change (e.g. uncheck “Has stairs”), wizard steps **rebuild** on the next render; previously rated hidden items remain in `ratings` but do not affect completion %.

---

## Scoring interaction

- **Completion %** = rated applicable items ÷ total applicable items  
- **SafeHome Score™** = earned ÷ max weight of applicable items (N/A excluded from both)  
- Section header shows **pts / applicable section weight** (not full static section max if items were skipped)

---

## Adding new rules (developers)

1. Add rule id to `ConditionalRuleId` in `conditional-rules.ts`  
2. Implement in `evaluateConditionalRule()`  
3. Export a `RULE.*` constant  
4. Attach to items in `safehome360-rubric.ts`:

```ts
itemSkipWhen: {
  "My checklist label": RULE.STAIRS,
}
```

Or hide a whole section:

```ts
buildSection("id", "Title", sectionNum, points, groups, RULE.BALCONY)
```

5. Add intake UI field in `AssessmentIntakeForm.tsx` if a new profile flag is needed  
6. Extend `ResidentProfile` in `resident-profile.ts`  
7. Add tests in `conditional.test.ts`

---

## Tests

```bash
cd frontend && npm test -- lib/livewell/conditional.test.ts
```

Covers: stairs, wheelchair, smart-home basic vs advanced, balcony section removal, solo-living items, apartment profile question reduction.

---

## Related

- [SAFEHOME360_ASSESSMENT.md](./SAFEHOME360_ASSESSMENT.md) — full assessment framework  
- [README.md](./README.md) — apps and admin URLs  
