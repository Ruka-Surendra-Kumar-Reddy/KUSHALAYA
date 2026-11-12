import { describe, expect, it } from "vitest";

import { buildAdminNavGroups, verticalNavLayout } from "@workforceos/contracts/shell";
import { VERTICALS } from "@workforceos/contracts";
import { buildAdminNavGroups as appBuildAdminNavGroups } from "./i18n/nav";
import { verticalNavLayout as appVerticalNavLayout } from "./verticalUx";

const t = (key: string) => key;

describe("workforceos shell re-exports", () => {
  it("app nav builder matches core package for Elder Care", () => {
    const core = buildAdminNavGroups(t, VERTICALS.ELDER_CARE, "US");
    const app = appBuildAdminNavGroups(t, VERTICALS.ELDER_CARE, "US");
    expect(app).toEqual(core);
  });

  it("LiveWell360 app nav matches core Care delivery layout", () => {
    const app = appBuildAdminNavGroups(t, VERTICALS.LIVEWELL360, "US");
    const appHrefs = app.flatMap((g) => g.items.map((i) => i.href));
    expect(appHrefs).toContain("/kushalaya/customers");
    expect(appHrefs).toContain("/kushalaya/assessments");
    expect(appHrefs).toContain("/kushalaya/visits");
    expect(app.some((g) => g.title === "nav.groups.liveWellCustomersGroup")).toBe(true);
  });

  it("app verticalUx delegates to core", () => {
    expect(appVerticalNavLayout(VERTICALS.HOUSEKEEPING)).toBe(
      verticalNavLayout(VERTICALS.HOUSEKEEPING),
    );
  });
});

describe("Kushalaya ops menu (customer journey, 2026-10-26)", () => {
  async function menu(role: string) {
    const { augmentNavGroupsForRole, isNavItemEnabled } = await import("@workforceos/contracts/shell");
    const auth = await import("./auth");
    const nav = await import("./i18n/nav");
    const groups = nav.withoutRetiredOpsNav(
      nav.filterNavGroupsForLiveWellRole(
        augmentNavGroupsForRole({
          groups: appBuildAdminNavGroups(t, VERTICALS.LIVEWELL360, "IN"),
          t,
          role,
          vertical: VERTICALS.LIVEWELL360,
          canAccessSettings: auth.canAccessSettings,
          canViewTeam: auth.canViewTeam,
          canManageUsers: auth.canManageUsers,
          canManageTenants: auth.canManageTenants,
          isNavItemEnabled,
        }),
        role,
        t,
      ),
    );
    return groups.map((g) => `${g.title}: ${g.items.map((i) => i.href).join(" ")}`);
  }

  it("gives admins Today, Sales, Customers, Business and Team & setup", async () => {
    expect(await menu("TENANT_ADMIN")).toEqual([
      "nav.groups.liveWellToday: /dashboard /kushalaya/alerts /kushalaya/messages",
      "nav.groups.liveWellSales: /kushalaya/enquiries /kushalaya/assessments /kushalaya/vendors /kushalaya/targets",
      "nav.groups.liveWellCustomersGroup: /kushalaya/customers /kushalaya/visits /kushalaya/room-checks",
      "nav.groups.liveWellBusiness: /kushalaya/owner /kushalaya/invoices /kushalaya/catalog /kushalaya/coupons /kushalaya/blog",
      "nav.groups.liveWellSetup: /users /kushalaya/hiring /kushalaya/iot-devices /kushalaya/rubric /settings",
    ]);
  });

  it("gives viewers Today, Assessments and Customers only", async () => {
    const m = await menu("VIEWER");
    expect(m.join(" ")).not.toContain("/kushalaya/enquiries");
    expect(m.join(" ")).not.toContain("/kushalaya/hiring");
    expect(m.join(" ")).toContain("/kushalaya/assessments");
    expect(m.join(" ")).toContain("/kushalaya/customers");
  });

  it("gives managers no Business, Wearables or Assessment questions", async () => {
    expect(await menu("CARE_MANAGER")).toEqual([
      "nav.groups.liveWellToday: /dashboard /kushalaya/alerts /kushalaya/messages",
      "nav.groups.liveWellSales: /kushalaya/enquiries /kushalaya/assessments /kushalaya/vendors /kushalaya/targets",
      "nav.groups.liveWellCustomersGroup: /kushalaya/customers /kushalaya/visits /kushalaya/room-checks",
      "nav.groups.liveWellSetup: /users /kushalaya/hiring /settings",
    ]);
  });
});
