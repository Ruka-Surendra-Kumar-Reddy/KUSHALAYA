# Kushalaya (SafeHomeOps)

Kushalaya is the default **public brand** of **SafeHomeOps** (`DEPLOY_VERTICAL=LIVEWELL360`).
Display name is configurable via `NEXT_PUBLIC_BRAND_NAME` / `BRAND_NAME` — see [../BRAND.md](../BRAND.md).
App routes live under `/livewell`; Python package `app.livewell`.

## Documentation

| Doc | Contents |
|-----|----------|
| **[FAMILY_PORTAL_USER_GUIDE.md](./FAMILY_PORTAL_USER_GUIDE.md)** | Family PWA — all features (score, plan, schedule, chat, circle, digests, SOS, multi-elder) |
| **[ASSESSOR_ITEM_TRAINING.md](./ASSESSOR_ITEM_TRAINING.md)** | Per-item assessor training — what to look for & how to rate Excellent / Acceptable / Unsafe / N/A |
| **[CUSTOMER_SIGNED_DOCUMENTS.md](./CUSTOMER_SIGNED_DOCUMENTS.md)** | Paper pack print + wet-signed scan upload |
| **[SAFEHOME360_ASSESSMENT.md](./SAFEHOME360_ASSESSMENT.md)** | Assessment framework — wizard, scoring, grades, Safety Age™, data model |
| **[SOLUTION_CATALOG_PRICING.md](./SOLUTION_CATALOG_PRICING.md)** | Solution library, product catalog, pricing engine, master spreadsheet, quotes |
| **[OPS_PORTAL_NAV.md](./OPS_PORTAL_NAV.md)** | Ops sidebar sections, apps vs shells, role visibility matrix |
| **[ADMIN_FUNCTIONAL_OVERVIEW.html](./ADMIN_FUNCTIONAL_OVERVIEW.html)** | Full admin functional overview for developers (open in browser → Print → PDF) |
| **[MANUAL_TEST_CASES.html](./MANUAL_TEST_CASES.html)** | Manual QA test cases — 80+ step-by-step checks (Print → PDF) |
| **[IOT_B7_MG7_ROADMAP.md](./IOT_B7_MG7_ROADMAP.md)** | Minew B7 + MG7 SOS via Mosquitto (MQTT-first) |
| **[IOT_B7_MG7_FIELD_SETUP.md](./IOT_B7_MG7_FIELD_SETUP.md)** | Field guide: configure B7 + MG7 with LiveWell |
| **[IOT_B7_MG7_ARCHITECTURE.md](./IOT_B7_MG7_ARCHITECTURE.md)** | Processes/services and how they interact with B7/MG7 |
| **[IOT_PILOT_IMPLEMENTATION.md](./IOT_PILOT_IMPLEMENTATION.md)** | Pilot build plan — **gated after initial SOS validation** (install, escalate, monitor, support) |
| **[../../deploy/mqtt/SERVER_SETUP.md](../../deploy/mqtt/SERVER_SETUP.md)** | Server install scripts + runbook |
| **[CONDITIONAL_LOGIC.md](./CONDITIONAL_LOGIC.md)** | Profile-driven show/hide rules — which questions appear and why |
| **[../livewell360/KAA_SPEC.md](../livewell360/KAA_SPEC.md)** | KAA Assessment Spec |
| **[../../deploy/nginx/README.md](../../deploy/nginx/README.md)** | Nginx + Let's Encrypt (`livewell` marketing + `livewellops` ops) |

---

## Apps & URLs

**Marketing:** [`https://www.kushalaya.com`](https://www.kushalaya.com) (public homepage)  
**Ops / portal:** [`https://ops.kushalaya.com`](https://ops.kushalaya.com)  
Legacy [`https://ops.kushalaya.com`](https://ops.kushalaya.com) → 301 to livewellops.  
Legacy [`https://www.kushalaya.com`](https://www.kushalaya.com) → 301 to livewell.

Public paths for ops apps are under **`/livewell`** (`/home-safety` redirects).

Install assessor or family portal via **Add to Home Screen** on mobile.

### Customer / field-facing

| App | Production URL | Users |
|-----|----------------|-------|
| **Family marketing homepage** | https://www.kushalaya.com/ | Families / NRI |
| **Assessor PWA** | https://ops.kushalaya.com/livewell | Field assessors |
| **New / list assessments** | https://ops.kushalaya.com/livewell/assess | Assessors |
| **Assessment wizard** | https://ops.kushalaya.com/livewell/assess/{id} | Assessors |
| **Scoring & training** | https://ops.kushalaya.com/livewell/scoring | Assessors |
| **Product showcase** | https://ops.kushalaya.com/livewell/showcase | Families / sales (often `?tenant_id=…`) |
| **Family login** | https://ops.kushalaya.com/livewell/family/login | Family portal role |
| **Family home** | https://ops.kushalaya.com/livewell/family | → dashboard |
| **Family dashboard** | https://ops.kushalaya.com/livewell/family/dashboard | Home (score, share, priorities) |
| **Family schedule / updates / chat / more** | https://ops.kushalaya.com/livewell/family/{schedule,updates,messages,more} | Care hub primary tabs |
| **Family score / plan / photos / wellness / contacts** | https://ops.kushalaya.com/livewell/family/{safety,plan,photos,wellness,contacts} | Under More |
| **Family alerts / circle / digests / documents / visits** | https://ops.kushalaya.com/livewell/family/{alerts,circle,digests,documents,visits} | Under More + history |

### Staff admin (after `/login`)

Sidebar sections (Care delivery, Catalog & quotes, …) and role visibility: **[OPS_PORTAL_NAV.md](./OPS_PORTAL_NAV.md)**.

| Page | Path |
|------|------|
| Clients | `/livewell/customers` |
| Assessments | `/livewell` |
| Visits & check-ins | `/livewell/visits` |
| KAA checklist | `/livewell/rubric` |
| Solution library | `/livewell/solutions` |
| Product catalog | `/livewell/catalog` |
| Pricing | `/livewell/pricing` |
| Partners | `/livewell/partners` |
| Vendors | `/livewell/suppliers` |
| **Configuration workbook** | `/livewell/master-data` |
| AI visualization jobs | `/livewell/ai-jobs` |
| Agency dashboard | `/dashboard` |

---

## Commercial pipeline (summary)

```
Finding (Unsafe/Acceptable) → Solution (SH-*) → Product (SKU) → Quote (₹)
```

| Step | What happens |
|------|----------------|
| **Assess** | Rate checklist items; conditional logic hides irrelevant questions |
| **Improvement plan** | Unsafe/Acceptable items match solutions via `rubricItemIds` |
| **Product quote** | Solutions resolve catalog SKUs via `solution_ids` |
| **Grand total** | Pricing config applies labor, travel, margin, GST |
| **Master data** | Import/export Excel sheets (rubric, solutions, catalog, suppliers, pricing) |

Full detail: [SOLUTION_CATALOG_PRICING.md](./SOLUTION_CATALOG_PRICING.md)

---

## Frontend layout

| Path | Purpose |
|------|---------|
| `frontend/app/livewell/` | Assessor PWA routes |
| `frontend/app/livewell/family/` | Family dashboard PWA (care hub) |
| `frontend/app/(app)/livewell/` | Admin (rubric, solutions, catalog, pricing, suppliers, master-data, visits) |
| `frontend/components/livewell/` | UI (wizard, intake, ratings, quote panel, admin editors, family shell) |
| `frontend/lib/livewell/` | Rubric, scoring, solutions, catalog, pricing, family APIs |

Key libraries:

- `safehome360-rubric.ts` — default checklist (13 scored sections)
- `assessment.ts` — SafeHome Score™, grades, reports
- `improvement-plan.ts` — solution matching from findings
- `product-recommendations.ts` — catalog SKU resolution
- `pricing-engine.ts` — margin, labor, travel, GST, grand total
- `supplier-workbook.ts` — supplier CSV/JSON import/export
- `masterDataApi.ts` — Excel master workbook import → stage → approve
- `conditional-rules.ts` + `conditional.ts` — show/hide engine
- `assessFlow.ts` — wizard steps

---

## Backend

| Path / API | Purpose |
|------------|---------|
| `backend/app/livewell/` | Family, catalog, solutions, pricing, suppliers, master workbook, visits, photos |
| `GET /api/v1/home-safety/family/*` | Family app |
| `GET/PUT /api/v1/home-safety/solutions` | Solution library (tenant) |
| `GET/PUT /api/v1/home-safety/catalog` | Product catalog (tenant) |
| `GET /api/v1/home-safety/catalog/public` | Showcase (`tenant_id` param) |
| `GET/PUT /api/v1/home-safety/pricing` | Pricing configuration (tenant) |
| `GET/PUT /api/v1/home-safety/suppliers` | Supplier directory (tenant) |
| `GET/POST /api/v1/home-safety/master-data/*` | Excel export/import/stage/approve/seed |
| `GET/POST /api/v1/home-safety/visits` | Staff visit log |
| `POST /api/v1/home-safety/photos` | Assessment / visit photos |

Canonical seed workbook: `backend/app/livewell/data/Kushalaya_Configuration.xlsx`

**Pilot launch workbook** (trimmed commercial catalog — Safety Assessment, Safety Installation SKUs, Family Peace-of-Mind):  
`backend/app/livewell/data/Kushalaya_Configuration_Pilot.xlsx`  

Rebuild with: `python scripts/build_pilot_master_workbook.py` from `backend/`. Import via **Master data** → stage → approve → seed.  

Photos: ProductIDs/ProductCodes stay stable (`BTH-001`, `SVC-001`, …). On approve, the app **merges** existing `image_ids` and **relinks** orphaned catalog image Documents. If some SKUs still lack photos after import, run:

`python scripts/relink_catalog_product_photos.py --confirm`  

and/or  

`python scripts/seed_catalog_product_type_photos.py --only-missing --confirm`
Seed via Master Data UI or `POST /api/v1/home-safety/master-data/seed-defaults`.

Tenant overrides are stored in `tenant.workflow_config` keys: `home_safety_solutions`, `home_safety_catalog`, `home_safety_pricing`, `home_safety_suppliers`, etc.

Family data: client spine `custom_attributes.safe_home` (score, wellness, visits) plus family portal services for alerts and photos.

---

## Assessor workflow (summary)

1. **+ New** on `/home-safety` → opens wizard  
2. **Resident profile** — intake; conditional logic hides irrelevant sections ([CONDITIONAL_LOGIC.md](./CONDITIONAL_LOGIC.md))  
3. **Scored sections** — rate each item ★ / ~ / ✕ / —  
4. **Photos** — before images for findings  
5. **Review & save** — score, **improvement plan**, **customer quote**, assessor notes, finalize  
6. Draft auto-saves locally; **Save** requires 100% of applicable items + resident first name  
7. When signed in, save syncs to **prospect pipeline** (report includes quote text) and uploads photos  

Full detail: [SAFEHOME360_ASSESSMENT.md](./SAFEHOME360_ASSESSMENT.md)

---

## Family app

Full guide: **[FAMILY_PORTAL_USER_GUIDE.md](./FAMILY_PORTAL_USER_GUIDE.md)**

1. Login at `/livewell/family/login` with Family credentials from your Kushalaya team  
2. **Home** — Independence Score™, pathway, next visit, share update, top priorities  
3. **Schedule** — visits + request services (staff confirm)  
4. **Updates / Chat** — care timeline and two-way messaging  
5. **More** — alerts & SOS, family circle, digests, documents, score, living plan, photos & approved AI visuals, wellness, emergency contacts  
6. **Viewing** switcher — one login can cover multiple seniors  

Completing an assessment linked to a client (or converting an open lead → client) publishes score + plan to the family app. Conversion absorbs the lead; the client is the sole identity afterward.

---

## Product catalog & showcase

- **Admin** `/home-safety/catalog` — default SKUs, solution links, packages, multi-photo upload  
- **Master data** `/home-safety/master-data` — full Excel pipeline (sheets for rubric, solutions, products, suppliers, pricing)  
- **Showcase** `/home-safety/showcase` — family-facing packages from public API  
- **Reset defaults → Save** or **Seed from master spreadsheet** loads the full catalog on a tenant  
- Products/packages SoT: edit `Kushalaya_Configuration.xlsx`, then `python backend/scripts/sync_catalog_defaults_from_workbook.py`  
- **Photos:** upload in Catalog UI, or `python -m app.create_catalog_images --from-dir … --confirm`  
  (see [SAFEHOME_SEED.md](../SAFEHOME_SEED.md#catalog-showcase-photos); migrate from another DB with `--from-db`)  

---

## Scoring (quick reference)

| Rating | Points |
|--------|--------|
| Excellent | 100% of item weight |
| Acceptable | 50% |
| Unsafe | 0% |
| N/A | Excluded from score |

**SafeHome Score™:** 0–100 normalized across applicable items.

| Score | Grade |
|-------|-------|
| 95+ | Platinum |
| 85+ | Gold |
| 75+ | Silver |
| 65+ | Bronze |
| &lt;65 | Red |

---

## Planned (Phase D+)

- Installer masters, regional labor rates, quote approval workflow  
- Server-side assessment storage & family sync of live quotes  
- PDF family report  
