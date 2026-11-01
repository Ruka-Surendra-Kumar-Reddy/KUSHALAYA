import { describe, expect, it } from "vitest";

import { VERTICALS, type VerticalId } from "./platform";
import {
  isNavItemEnabled,
  isPathAllowedForVertical,
  verticalHasFeature,
} from "./features";
import { buildAdminNavGroups } from "./i18n/nav";

const t = (key: string) => key;

/** Routes gated by a single feature for every vertical. */
const GATED_ADMIN_ROUTES: { path: string; feature: string }[] = [
  { path: "/elders", feature: "elders" },
  { path: "/elders/new", feature: "elders" },
  { path: "/elders/42", feature: "elders" },
  { path: "/matching", feature: "elder_matching" },
  { path: "/billing", feature: "elder_billing" },
  { path: "/monitoring", feature: "monitoring" },
  { path: "/monitoring/alerts", feature: "monitoring" },
  { path: "/monitoring/config", feature: "monitoring" },
  { path: "/cleaning", feature: "cleaning_properties" },
  { path: "/cleaning/leads", feature: "cleaning_crm" },
  { path: "/cleaning/quotes", feature: "cleaning_price_book" },
  { path: "/cleaning/dispatch", feature: "cleaning_dispatch" },
  { path: "/cleaning/customers", feature: "cleaning_crm" },
  { path: "/cleaning/price-book", feature: "cleaning_price_book" },
  { path: "/communications/requests", feature: "communications" },
  { path: "/kushalaya/visits", feature: "livewell" },
  { path: "/kushalaya/catalog", feature: "livewell" },
  { path: "/kushalaya/rubric", feature: "livewell" },
  { path: "/kushalaya/solutions", feature: "livewell" },
  { path: "/kushalaya/pricing", feature: "livewell" },
  { path: "/kushalaya/partners", feature: "livewell" },
  { path: "/kushalaya/activity", feature: "livewell" },
  { path: "/kushalaya/suppliers", feature: "livewell" },
  { path: "/kushalaya/master-data", feature: "livewell" },
  { path: "/kushalaya/ai-jobs", feature: "livewell" },
];

/** Shared workforce routes — allowed for every vertical. */
const SHARED_ADMIN_ROUTES = [
  "/dashboard",
  "/executive",
  "/workforce",
  "/workforce?tab=bench",
  "/copilot",
  "/prospects",
  "/caregivers",
  "/caregivers/new",
  "/caregivers/1",
  "/scheduling",
  "/attendance",
  "/attendance/simulator",
  "/documents",
  "/payroll",
  "/users",
  "/settings",
  "/settings/workflows",
  "/academy/marketplace",
];

const ALL_VERTICALS: VerticalId[] = [
  VERTICALS.ELDER_CARE,
  VERTICALS.HOUSEKEEPING,
  VERTICALS.SECURITY,
  VERTICALS.DRIVER_SERVICES,
  VERTICALS.HOME_HEALTHCARE,
  VERTICALS.LIVEWELL360,
];

describe("isPathAllowedForVertical", () => {
  for (const { path, feature } of GATED_ADMIN_ROUTES) {
    it(`allows ${path} only when vertical has ${feature}`, () => {
      for (const vertical of ALL_VERTICALS) {
        const allowed = isPathAllowedForVertical(path, vertical);
        expect(allowed).toBe(verticalHasFeature(vertical, feature));
      }
    });
  }

  it("allows /assignments for elder care (elders) and housekeeping (customer_spine)", () => {
    expect(isPathAllowedForVertical("/assignments", VERTICALS.ELDER_CARE)).toBe(true);
    expect(isPathAllowedForVertical("/assignments", VERTICALS.HOUSEKEEPING)).toBe(true);
    expect(isPathAllowedForVertical("/assignments", VERTICALS.SECURITY)).toBe(false);
  });

  it("allows shared routes for every vertical", () => {
    for (const vertical of ALL_VERTICALS) {
      for (const path of SHARED_ADMIN_ROUTES) {
        expect(isPathAllowedForVertical(path, vertical)).toBe(true);
      }
    }
  });
});

describe("nav hrefs vs route guard", () => {
  function navHrefs(vertical: VerticalId): string[] {
    return buildAdminNavGroups(t, vertical, "US").flatMap((g) =>
      g.items.map((i) => i.href),
    );
  }

  for (const vertical of ALL_VERTICALS) {
    it(`only exposes allowed links for ${vertical}`, () => {
      for (const href of navHrefs(vertical)) {
        expect(isPathAllowedForVertical(href, vertical)).toBe(true);
        expect(isNavItemEnabled(href, vertical)).toBe(true);
      }
    });
  }

  it("housekeeping nav never includes elder-only items", () => {
    const hrefs = navHrefs(VERTICALS.HOUSEKEEPING);
    expect(hrefs).not.toContain("/elders");
    expect(hrefs).not.toContain("/matching");
    expect(hrefs).not.toContain("/monitoring");
    expect(hrefs).not.toContain("/billing");
    expect(hrefs.some((h) => h.startsWith("/kushalaya"))).toBe(false);
    expect(hrefs.some((h) => h.startsWith("/cleaning"))).toBe(true);
    expect(hrefs).toContain("/communications/requests");
  });

  it("elder care nav includes service requests and elder routes, never cleaning or livewell", () => {
    const hrefs = navHrefs(VERTICALS.ELDER_CARE);
    expect(hrefs).toContain("/communications/requests");
    expect(hrefs).toContain("/elders");
    expect(hrefs).toContain("/matching");
    expect(hrefs.some((h) => h.startsWith("/cleaning"))).toBe(false);
    expect(hrefs.some((h) => h.startsWith("/kushalaya"))).toBe(false);
  });

  it("livewell360 nav includes livewell admin routes", () => {
    const hrefs = navHrefs(VERTICALS.LIVEWELL360);
    expect(hrefs).toContain("/kushalaya/visits");
    expect(hrefs).toContain("/kushalaya/assessments");
    expect(hrefs).toContain("/kushalaya/catalog");
    expect(hrefs).toContain("/kushalaya/rubric");
    expect(hrefs).not.toContain("/kushalaya/master-data"); // retired, see lib/ops-retired.ts
    expect(hrefs).not.toContain("/elders");
  });

  it("placeholder verticals never include industry-specific nav", () => {
    for (const vertical of [
      VERTICALS.SECURITY,
      VERTICALS.DRIVER_SERVICES,
      VERTICALS.HOME_HEALTHCARE,
    ]) {
      const hrefs = navHrefs(vertical);
      expect(hrefs.some((h) => h.startsWith("/cleaning"))).toBe(false);
      expect(hrefs).not.toContain("/elders");
      expect(hrefs).not.toContain("/matching");
      expect(hrefs).not.toContain("/monitoring");
      expect(hrefs).not.toContain("/billing");
      expect(hrefs.some((h) => h.startsWith("/kushalaya"))).toBe(false);
    }
  });
});
