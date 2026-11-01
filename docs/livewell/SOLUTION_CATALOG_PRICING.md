# SafeHome 360™ — Solutions, Catalog & Pricing

**Version:** 1.0 (Phases A–C + suppliers + master workbook shipped)  
**Product:** SafeHome 360™ commercial pipeline in **SafeHomeOps**

This document describes how assessment findings flow into corrective actions, installable products, and customer quotes.

---

## Pipeline overview

```
Assessment finding (Unsafe / Acceptable)
        ↓
Solution library (SH-*)
        ↓
Product catalog (BTH-*, EXT-*, … via solution_ids)
        ↓
Pricing engine (margin, labor, travel, GST)
        ↓
Customer quote (assess review + report)
        ↓
[Planned] Approval → work order → invoice
```

| Phase | Scope | Status |
|-------|--------|--------|
| **A** | Product catalog + `solution_ids` links + admin | Shipped |
| **B** | Product recommendations from improvement plan | Shipped |
| **C** | Configurable pricing engine + quote on review | Shipped |
| **Suppliers** | Supplier directory, preferred offers, workbook I/O | Shipped |
| **Master data** | Excel export / import → stage → approve → seed | Shipped |
| **D+** | Installers, regional rates, quote entity & WO/PO | Planned |

---

## Admin URLs

| Page | URL | Purpose |
|------|-----|---------|
| Checklist | `/home-safety/rubric` | SafeHome 360™ rubric (assessment items) |
| Solution library | `/home-safety/solutions` | Findings → corrective actions (`SH-*`) |
| Product catalog | `/home-safety/catalog` | SKUs, packages, solution links |
| Pricing | `/home-safety/pricing` | Margin, labor, travel, GST, surcharges |
| Suppliers | `/home-safety/suppliers` | Vendor directory & product offers |
| Master spreadsheet | `/home-safety/master-data` | Import/export canonical Excel workbook |
| Visits | `/home-safety/visits` | Log Safe Home field visits |
| Showcase | `/home-safety/showcase` | Family-facing packages (public API) |

All admin pages are linked from **Settings → Home safety assessments** and the Safe Home sidebar group.

---

## 1. Solution library

Maps rubric items rated **Unsafe** or **Acceptable** to standardized corrective actions.

### Data model (`SafeHomeSolution`)

| Field | Purpose |
|-------|---------|
| `id` | e.g. `SH-BTH-001` |
| `finding` / `riskDescription` | Human-readable problem |
| `priority` | `critical` \| `high` \| `medium` \| `low` |
| `recommendedSolutions` | Action bullets for assessors |
| `contractorType` | Installer type label (text) |
| `estimatedCost` / `installationTime` | Display + labor estimation |
| `scoreImprovement` | Projected SafeHome Score™ gain |
| `rubricItemIds` | Triggers when these items are Unsafe/Acceptable |

**Default:** 29 solutions in `solution-defaults.ts` / `default_solutions.json`.

### Storage

| Layer | Key / path |
|-------|------------|
| Frontend cache | `localStorage` `safehome_home_safety_solutions_v1` (legacy: `eldercare_home_safety_solutions_v1`) |
| Backend (tenant) | `workflow_config.home_safety_solutions` |
| API | `GET/PUT /api/v1/home-safety/solutions` |

### Engine

`buildImprovementPlan()` in `improvement-plan.ts` — shown on assess **Review** in `ImprovementPlanPanel`.

---

## 2. Product catalog (Phase A)

Installable SKUs linked back to solutions.

### Data model (`CatalogProduct`)

Core showcase fields: `name`, `short_description`, `category`, `price_inr`, images.

Spec / commercial fields (Phase A):

| Field | Example |
|-------|---------|
| `product_code` | `BTH-001` |
| `category_prefix` | `BTH`, `EXT`, `LIV`, … |
| `purpose`, `options`, `material` | Product detail |
| `contractor_type`, `install_time` | Install metadata |
| `product_cost`, `installed_price` | Cost strings |
| `safety_improvement` | Score gain if installed |
| `solution_ids` | `["SH-BTH-001", "SH-BTH-002"]` |

**Default:** 63 SKUs in `catalog-product-seed.ts` / `default_catalog.json` (48 linked to solutions).

### Packages

Bundles for showcase: **Assessment Only**, **Essential**, **Safe Living**, **Premium Independence** — curated `product_ids` + marketing `price_inr`.

### Storage

| Layer | Key / path |
|-------|------------|
| Frontend cache | `localStorage` `safehome_home_safety_catalog_v2` (legacy: `eldercare_home_safety_catalog_v*`) |
| Backend (tenant) | `workflow_config.home_safety_catalog` |
| API | `GET/PUT /api/v1/home-safety/catalog` |
| Public showcase | `GET /api/v1/home-safety/catalog/public?tenant_id=` |

### Admin UI

`CatalogProductsAdmin` — expandable SKU editor grouped by category prefix; checkbox links to solution library entries.

**Load full catalog on a tenant:** `/home-safety/catalog` → **Reset defaults** → **Save catalog**.

---

## 3. Product recommendations (Phase B)

When the improvement plan lists solutions, the engine resolves catalog products:

```
productsForSolution(products, solutionId)
  → filter catalog where solution_ids includes solutionId
```

`buildProductRecommendations(plan, catalog)`:

- Collects products for each matched solution
- **Dedupes** by product id (merges solution references)
- Sorts by solution priority, then SKU
- Computes line totals from `price_inr` or parsed `installed_price`
- Flags solutions with no linked products

---

## 4. Pricing engine (Phase C)

Applies tenant-configurable rates to the product quote draft.

### Configuration (`SafeHomePricingConfig`)

Factory defaults (Hyderabad baseline) in `pricing-defaults.ts`:

| Setting | Default |
|---------|---------|
| Default margin | 25% (min 15%, max 50%) |
| Margin type | `percent` or `fixed` |
| Labor rate | ₹700/hour |
| Default hours per solution | 2h |
| Travel rate | ₹15/km |
| Minimum service charge | ₹500 |
| Default consumables | ₹500 |
| GST | 18% |
| Weekend / emergency surcharge | 15% / 25% |
| Round-off | Nearest ₹100 |

### Storage

| Layer | Key / path |
|-------|------------|
| Frontend cache | `localStorage` `safehome_home_safety_pricing_v1` (legacy: `eldercare_home_safety_pricing_v1`) |
| Backend (tenant) | `workflow_config.home_safety_pricing` |
| API | `GET/PUT /api/v1/home-safety/pricing` |

### Formula

```
costSubtotal = products + labor + travel + consumables + misc
             + weekend surcharge (optional)
             + emergency surcharge (optional)

margin       = percent × costSubtotal  OR  fixed ₹ amount
preTax       = costSubtotal + margin
gst          = preTax × gst%
grandTotal   = round(preTax + gst)  // nearest ₹50 or ₹100
```

**Labor hours** — estimated from each matched solution’s `installationTime` (parsed), else `default_labor_hours_per_solution`. Assessor can override on review.

**Minimum service charge** — if labor hours > 0 and labor + travel < minimum, labor is bumped to meet the floor.

### Assessor review (`ProductQuoteDraftPanel`)

On assess **Review**, after the improvement plan:

- Product line items + solution tags
- Overrides: travel km, labor hours, weekend/emergency surcharges
- Full breakdown: products, labor, travel, consumables, margin, GST, grand total
- Plain-text quote for copy / share / prospect activity

---

## 5. Reports & pipeline

`formatAssessmentReport()` appends, when solutions + catalog (+ pricing) are available:

1. Improvement plan (solutions)
2. Product line items
3. Customer quote estimate (margin + GST)

`syncAssessmentToProspect()` includes the full report (with quote) as a prospect activity when the assessor is signed in.

---

## Code map

| Concern | File(s) |
|---------|---------|
| Solution types & defaults | `solution-types.ts`, `solution-defaults.ts` |
| Improvement plan | `improvement-plan.ts`, `ImprovementPlanPanel.tsx` |
| Catalog types & seed | `catalog-types.ts`, `catalog-defaults.ts` (from workbook JSON), `generated/catalog-from-workbook.json` |
| Product recommendations | `product-recommendations.ts` |
| Pricing config & engine | `pricing-types.ts`, `pricing-defaults.ts`, `pricing-engine.ts` |
| Suppliers | `supplier-types.ts`, `suppliers.ts`, `supplier-workbook.ts`, `SuppliersAdminEditor.tsx` |
| Master workbook | `masterDataApi.ts`, `MasterDataAdminEditor.tsx`, `master_data_service.py`, `master_data_workbook.py` |
| Quote UI | `ProductQuoteDraftPanel.tsx` |
| Admin editors | `SolutionsAdminEditor.tsx`, `CatalogProductsAdmin.tsx`, `PricingAdminEditor.tsx` |
| APIs (FE) | `solutionApi.ts`, `catalogApi.ts`, `pricingApi.ts`, `supplierApi.ts`, `masterDataApi.ts` |
| APIs (BE) | `solution_service.py`, `catalog_service.py`, `pricing_service.py`, `supplier_service.py`, `master_data_service.py` |
| Canonical xlsx | `backend/app/livewell/data/Kushalaya_Configuration.xlsx` (**source of truth** for products/packages) |
| Sync catalog JSON | `python backend/scripts/sync_catalog_defaults_from_workbook.py` |
| Tests | `improvement-plan.test.ts`, `catalog-product-seed.test.ts`, `product-recommendations.test.ts`, `pricing-engine.test.ts` |

---

## Item sources (rubric)

Checklist items are tagged with authoritative sources where applicable:

| Source | Badge |
|--------|-------|
| AARP | Home Fit Guide |
| CDC | STEADI / fall prevention |
| SafeHome 360™ | Proprietary |

See `rubric-sources.ts`, `RubricSourceBadge.tsx`.

---

## Planned (not yet built)

| Feature | Notes |
|---------|-------|
| Installer master | Skills, availability, per-job rates |
| Regional labor tables | City-specific rates |
| Quote entity & approval workflow | Ops review → customer sign-off |
| Work orders & POs | Post-approval execution (draft PO UI exists) |
| Server-side assessment storage | Assessments still in browser localStorage |
| PDF family report | Text report only today |
| Family-visible live quote | Family app sees score/visits, not quote |

---

## Related docs

- [README.md](./README.md) — vertical overview  
- [SAFEHOME360_ASSESSMENT.md](./SAFEHOME360_ASSESSMENT.md) — wizard, scoring, Safety Age™  
- [CONDITIONAL_LOGIC.md](./CONDITIONAL_LOGIC.md) — profile-driven question filtering
