import { describe, expect, it } from "vitest";

import { VERTICALS } from "./platform";
import {
  ALL_VERTICAL_IDS,
  dashboardSubtitleKey,
  prospectsPageSubtitle,
  verticalNavLayout,
  workforceListAddKey,
  workforceListPageKey,
} from "./verticalUx";
import { buildAdminNavGroups } from "./i18n/nav";

const t = (key: string) => key;

describe("verticalNavLayout", () => {
  it("maps each vertical to the correct shell layout", () => {
    expect(verticalNavLayout(VERTICALS.ELDER_CARE)).toBe("elder_care");
    expect(verticalNavLayout(VERTICALS.HOUSEKEEPING)).toBe("housekeeping");
    expect(verticalNavLayout(VERTICALS.SECURITY)).toBe("workforce_only");
    expect(verticalNavLayout(VERTICALS.DRIVER_SERVICES)).toBe("workforce_only");
    expect(verticalNavLayout(VERTICALS.HOME_HEALTHCARE)).toBe("workforce_only");
    expect(verticalNavLayout(VERTICALS.LIVEWELL360)).toBe("livewell360");
  });
});


describe("workforceListPageKey", () => {
  it("returns vertical-specific page keys", () => {
    expect(workforceListPageKey(VERTICALS.HOUSEKEEPING)).toBe("cleaners");
    expect(workforceListPageKey(VERTICALS.ELDER_CARE)).toBe("caregivers");
    expect(workforceListPageKey(VERTICALS.LIVEWELL360)).toBe("assessors");
    expect(workforceListPageKey(VERTICALS.SECURITY)).toBe("guards");
    expect(workforceListPageKey(VERTICALS.DRIVER_SERVICES)).toBe("drivers");
    expect(workforceListPageKey(VERTICALS.HOME_HEALTHCARE)).toBe("careTeam");
  });

  it("returns add-button i18n keys", () => {
    expect(workforceListAddKey(VERTICALS.SECURITY)).toBe("pages.guards.addGuard");
    expect(workforceListAddKey(VERTICALS.DRIVER_SERVICES)).toBe(
      "pages.drivers.addDriver",
    );
  });
});

describe("dashboardSubtitleKey", () => {
  it("selects subtitle keys per layout", () => {
    expect(dashboardSubtitleKey(VERTICALS.HOUSEKEEPING)).toBe(
      "pages.dashboard.subtitleHousekeeping",
    );
    expect(dashboardSubtitleKey(VERTICALS.ELDER_CARE)).toBe("pages.dashboard.subtitle");
    expect(dashboardSubtitleKey(VERTICALS.LIVEWELL360)).toBe(
      "pages.dashboard.subtitleLiveWell",
    );
    expect(dashboardSubtitleKey(VERTICALS.SECURITY)).toBe(
      "pages.dashboard.subtitleWorkforce",
    );
  });
});

describe("prospectsPageSubtitle", () => {
  it("uses vertical worker labels", () => {
    expect(prospectsPageSubtitle(VERTICALS.HOUSEKEEPING, "US", false)).toBe(
      "Cleaners recruitment prospects",
    );
    expect(prospectsPageSubtitle(VERTICALS.ELDER_CARE, "US", true)).toBe(
      "Clients and caregivers recruitment prospects",
    );
    expect(prospectsPageSubtitle(VERTICALS.LIVEWELL360, "IN", true)).toBe(
      "Clients and assessors recruitment prospects",
    );
  });
});

describe("buildAdminNavGroups vertical isolation", () => {
  function navHrefs(vertical: string): string[] {
    return buildAdminNavGroups(t, vertical, "US").flatMap((g) =>
      g.items.map((i) => i.href),
    );
  }

  it("excludes elder and cleaning routes for housekeeping", () => {
    const hrefs = navHrefs(VERTICALS.HOUSEKEEPING);
    expect(hrefs.some((h) => h.startsWith("/cleaning"))).toBe(true);
    expect(hrefs).not.toContain("/elders");
    expect(hrefs).not.toContain("/matching");
    expect(hrefs).not.toContain("/monitoring");
    expect(hrefs).not.toContain("/billing");
  });

  it("excludes elder and cleaning routes for workforce-only verticals", () => {
    for (const vertical of [
      VERTICALS.SECURITY,
      VERTICALS.DRIVER_SERVICES,
      VERTICALS.HOME_HEALTHCARE,
    ]) {
      const hrefs = navHrefs(vertical);
      expect(hrefs).not.toContain("/elders");
      expect(hrefs).not.toContain("/matching");
      expect(hrefs).not.toContain("/monitoring");
      expect(hrefs).not.toContain("/billing");
      expect(hrefs.some((h) => h.startsWith("/cleaning"))).toBe(false);
      expect(hrefs).toContain("/caregivers");
      expect(hrefs).toContain("/payroll");
    }
  });

  it("includes elder-care routes only for elder care", () => {
    const hrefs = navHrefs(VERTICALS.ELDER_CARE);
    expect(hrefs).toContain("/elders");
    expect(hrefs).toContain("/matching");
    expect(hrefs).toContain("/monitoring");
    expect(hrefs).toContain("/billing");
    expect(hrefs.some((h) => h.startsWith("/cleaning"))).toBe(false);
  });

  it("uses LiveWell routes only for LIVEWELL360", () => {
    const hrefs = navHrefs(VERTICALS.LIVEWELL360);
    expect(hrefs).toContain("/kushalaya/customers");
    expect(hrefs).toContain("/kushalaya/assessments");
    expect(hrefs).toContain("/kushalaya/visits");
    expect(hrefs).toContain("/kushalaya/catalog");
    expect(hrefs).not.toContain("/kushalaya/master-data"); // retired, see lib/ops-retired.ts
    expect(hrefs).not.toContain("/prospects");
    // Documents only attaches files to elders/caregivers, which this vertical never has.
    expect(hrefs).not.toContain("/documents");
    expect(hrefs).not.toContain("/elders");
    expect(hrefs).not.toContain("/matching");
    expect(hrefs).not.toContain("/monitoring");
    expect(hrefs.some((h) => h.startsWith("/cleaning"))).toBe(false);

    // Care-flow items should appear before catalog tooling.
    expect(hrefs.indexOf("/kushalaya/customers")).toBeLessThan(hrefs.indexOf("/kushalaya/catalog"));
    expect(hrefs.indexOf("/kushalaya/customers")).toBeLessThan(hrefs.indexOf("/kushalaya/visits"));
  });

  it("labels LiveWell care-flow nav for admins", () => {
    const groups = buildAdminNavGroups(t, VERTICALS.LIVEWELL360, "US");
    const items = groups.flatMap((g) => g.items);
    const customers = items.find((i) => i.href === "/kushalaya/customers");
    expect(customers?.label).toBe("nav.items.liveWellCustomers");
    const careGroup = groups.find((g) =>
      g.items.some((i) => i.href === "/kushalaya/customers"),
    );
    expect(careGroup?.title).toBe("nav.groups.liveWellCustomersGroup");
  });

  it("covers every registered vertical id", () => {
    expect(ALL_VERTICAL_IDS).toHaveLength(7);
    for (const vertical of ALL_VERTICAL_IDS) {
      expect(buildAdminNavGroups(t, vertical, "US").length).toBeGreaterThan(0);
    }
  });
});
