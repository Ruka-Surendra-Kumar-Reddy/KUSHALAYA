# Kushalaya content & implementation roadmap

Repo folder remains **SafeHomeOps**. Product brand is **Kushalaya**. Purge + reseed (no data migrators).

## Phase A — Brand & vertical ✅

- `DEPLOY_VERTICAL=LIVEWELL360`
- Feature `livewell` (replaces `home_safety` in nav gating; legacy alias retained)
- Routes `/livewell/*` (redirect from `/home-safety`)
- Pack id `livewell360`
- UI copy Kushalaya / Independence Score™

## Phase B — KAA rubric & scoring ✅

- 12 domains as assessment categories (`lwa-rubric.ts` / `default_rubric.json`) — **v2.1** (~83 items)
- Independence Score™ bands (90 / 75 / 60 / 40)
- Domain sub-scores on review
- v2.1 adds AARP/STEADI-aligned items (smoke/CO, rugs, zero-step, scald, fall-risk screen, advance directive) + matching solutions

## Phase C — Solutions / products / services / memberships ✅

- **Solution Library v1.0** IDs `LW-{CAT}-{SUB}-{nnn}` (e.g. `LW-HS-BTH-001`)
- Fields: name, subcategory, evidenceLevel (A/B/C), membershipImpact, aiVisualization, followUpDays, legacyIds
- Bathroom pack complete + remapped prior flat `LW-HS-00x` via `legacyIds`
- Service catalog additions (nursing, PT, caregiver / ECM coordination, …)
- Memberships: Independent Living, Assisted Living at Home, Premium Living360, NRI Family Peace of Mind
- Link products/services via ProductSolutions + packages (`mbr_*`); catalog remaps legacy solution IDs
- Regenerate library: `python backend/scripts/generate_solution_library_v1.py`

## Phase D — Rule Engine (scaffold) ✅

- Findings / Rule Master / Conditions / Actions sheets (19–24)
- Membership + ECM rules export/parse + seed defaults
- `configuration_version_id` on assessments; membership/ECM stamp on finalize
- Simulation UI — planned

## Domain → starter content

| Domain | Solutions | Catalog |
|--------|-----------|---------|
| Home Safety | LW-HS-{BTH,BED,KIT,LIV,ENT,STA}-* | BTH/EXT/… products |
| Mobility | LW-MOB-* | MOB products + PT service |
| Health & Wellness | LW-HL-* (was LW-HW) | WEL services |
| ADL | LW-ADL-* | Services + aids |
| IADL | LW-IADL-* | Services |
| Cognitive | LW-COG-* | Services |
| Social wellbeing | LW-SOC-* | Companion / engagement |
| Emergency | LW-EMG-* | EMG products |
| Home Maintenance | LW-HM-* (was LW-HC home) | Mod services |
| Healthcare coordination | LW-HC-* | Clinical coordination |
| Technology | LW-TECH-* | SMT products |
| Family Support | LW-FAM-* | ECM triggers |
| Property | LW-PM-* | Inspections / utilities |
| Financial & Benefits | LW-FIN-* | Benefits counseling |
| Wellness & Lifestyle | LW-WELL-* (was LW-LIFE) | Engagement services |

## Seed

```bash
python -m app.seed_livewell   # preferred alias
# or legacy: python -m app.seed_safehome
```

## Config workbook

`backend/app/livewell/data/Kushalaya_Configuration.xlsx`

```bash
python backend/scripts/build_master_workbook.py
cd frontend && node scripts/dump-livewell-defaults.mjs
```
