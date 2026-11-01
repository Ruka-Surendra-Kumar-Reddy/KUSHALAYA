# LiveWell ops portal navigation

Staff sidebar on the **ops** host (`ops.kushalaya.com` after `/login`). Family and assessor use **separate shells** and are not folded into this sidebar.

## Who uses which app

| App | Shell | Typical users | Entry |
|-----|-------|---------------|-------|
| **Ops portal** | `AppShell` sidebar | Care managers, tenant admins, viewers | `/dashboard` and LiveWell admin routes |
| **Assessor PWA** | `HomeSafetyShell` bottom nav | Field assessors | `/livewell` |
| **Family portal** | `FamilyShell` bottom nav | Family / NRI caregivers | `/livewell/family` |

Marketing (`www.kushalaya.com`) is public and unrelated to ops nav.

## Sidebar sections

Order matches the LiveWell overlay in `frontend/lib/i18n/nav.ts` (core contract: `workforceos-core/contracts/nav.json` → `livewell360`).

| Group | Items |
|-------|--------|
| **Overview** | Dashboard · Tenants (super admin only) |
| **Care delivery** | Clients · Assessments · Visits & check-ins · Session activity |
| **Catalog & quotes** | Product catalog · KAA checklist · Solution library · Pricing |
| **Partner network** | Partners · Vendors |
| **Platform tools** | Master data · AI visualizations |
| **People & documents** | Assessor recruits · Documents |
| **Admin** | Users / Team · Settings · Workflows |

Admin / Tenants are attached by `augmentNavGroupsForRole` in workforceos-core, then trimmed by `filterNavGroupsForLiveWellRole` in SafeHomeOps.

## Role visibility

| Role | Sees |
|------|------|
| **VIEWER** | Overview + Care delivery |
| **CARE_MANAGER** | + Partner network + People & documents + Admin (Team / Settings) |
| **TENANT_ADMIN** | All non-tenant groups (including Catalog & Platform + Users) |
| **SYSTEM_ADMIN** | Same as tenant admin + Tenants |

Page-level RBAC beyond nav visibility is out of scope for this matrix.

## Source of truth

1. Core layout: `workforceos-core/contracts/nav.json` (`livewell360.groups`)
2. LiveWell regroup + role filter: `frontend/lib/i18n/nav.ts`
3. Shell wiring: `frontend/components/AppShell.tsx`
4. Labels: `frontend/messages/en.json` (overlay) and `workforceos-core/contracts/messages/platform.*.json`

See also: [CARE_STABILITY.md](./CARE_STABILITY.md) (visits in Care delivery), [README.md](./README.md) (apps & URLs),
[ADMIN_FUNCTIONAL_OVERVIEW.html](./ADMIN_FUNCTIONAL_OVERVIEW.html) (developer handoff — print to PDF).
