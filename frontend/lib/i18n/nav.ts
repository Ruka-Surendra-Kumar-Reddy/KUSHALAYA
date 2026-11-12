import { isAdmin, isViewer as isViewerRole } from "@/lib/roles";
export {
  augmentNavGroupsForRole,
  buildWorkforceTabs,
  workforceTabFromParam,
  WORKFORCE_TAB_IDS,
  isNavActive,
  roleLabelFromKey,
  type NavGroup,
  type NavItem,
  type TranslateFn,
  type WorkforceTabId,
} from "@workforceos/contracts/shell";

import {
  buildAdminNavGroups as coreBuildAdminNavGroups,
  verticalNavLayout,
  type NavGroup,
  type NavItem,
  type TranslateFn,
} from "@workforceos/contracts/shell";
import { MENU_HIDDEN_PATHS, RETIRED_OPS_PATHS, isRetiredOpsPath } from "@/lib/ops-retired";

const LIVEWELL_VERTICALS = new Set(["LIVEWELL360", "SAFEHOME360"]);

/** Elders-only routes that must never appear on LiveWell ops nav. */
const ELDER_ONLY_HREFS = new Set([
  "/elders",
  "/matching",
  "/monitoring",
  "/billing",
  "/assignments",
  "/executive",
]);

/**
 * The ops menu follows the customer's journey (owner, 2026-10-26):
 *   Today:        Dashboard · SOS & alerts · Messages
  *   Sales:        Operations (lead pipeline) · Assessments · Vendors
 *   Customers:    Customers · Visits
 *   Business:     Owner dashboard · Invoices · Products · Coupons · Blog   (admins)
 *   Team & setup: Team · Hiring · Wearables · Assessment questions · Settings
 *                 (Wearables and Assessment questions are admin-only; Team and
 *                 Settings come from the core Admin group, so its role rules apply)
 * Viewers see Today, Assessments and Customers only.
 */
const TODAY_HREFS = ["/dashboard", "/kushalaya/alerts", "/kushalaya/messages"] as const;
const SALES_HREFS = ["/kushalaya/enquiries", "/kushalaya/assessments", "/kushalaya/vendors", "/kushalaya/targets"] as const;
const CUSTOMER_HREFS = ["/kushalaya/customers", "/kushalaya/visits", "/kushalaya/room-checks"] as const;
const BUSINESS_HREFS = [
  "/kushalaya/owner",
  "/kushalaya/invoices",
  "/kushalaya/catalog",
  "/kushalaya/coupons",
  "/kushalaya/blog",
] as const;
/** Setup items this vertical owns; /users and /settings are added by core. */
const SETUP_HREFS = ["/kushalaya/hiring", "/kushalaya/iot-devices", "/kushalaya/rubric"] as const;
const ADMIN_ONLY_HREFS = new Set<string>([...BUSINESS_HREFS, "/kushalaya/iot-devices", "/kushalaya/rubric"]);
/** Sales work viewers don't do. */
const VIEWER_HIDDEN_HREFS = new Set<string>(["/kushalaya/enquiries", "/kushalaya/hiring", "/kushalaya/targets"]);

/** Core-layout routes this vertical hides even when nav.json lists them. */
const HIDDEN_HREFS = new Set<string>(RETIRED_OPS_PATHS);

/** Final pass: drop retired pages from any group (Admin/Tenants are appended late). */
export function withoutRetiredOpsNav(groups: NavGroup[]): NavGroup[] {
  return groups
    .map((g) => ({
      ...g,
      items: g.items.filter((i) => {
        const href = normalizeLiveWellHref(i.href);
        return !isRetiredOpsPath(href) && !(MENU_HIDDEN_PATHS as readonly string[]).includes(href);
      }),
    }))
    .filter((g) => g.items.length > 0);
}

/** Group title keys of the ops menu. */
export const LIVEWELL_NAV_GROUP_KEYS = {
  today: "nav.groups.liveWellToday",
  sales: "nav.groups.liveWellSales",
  customers: "nav.groups.liveWellCustomersGroup",
  business: "nav.groups.liveWellBusiness",
  setup: "nav.groups.liveWellSetup",
} as const;

function normalizeLiveWellHref(href: string): string {
  if (href === "/home-safety" || href === "/kushalaya") return "/kushalaya/assessments";
  if (href.startsWith("/home-safety/")) {
    return `/kushalaya/${href.slice("/home-safety/".length)}`;
  }
  return href;
}

function labelForHref(href: string, t: TranslateFn): string {
  const n = normalizeLiveWellHref(href);
  const map: Record<string, string> = {
    "/dashboard": t("nav.items.dashboard"),
    "/kushalaya/alerts": t("nav.items.liveWellAlerts"),
    "/kushalaya/messages": t("nav.items.liveWellFamilyMessages"),
    "/kushalaya/customers": t("nav.items.liveWellCustomers"),
    "/kushalaya/assessments": t("nav.items.liveWellAssessments"),
    "/kushalaya/visits": t("nav.items.liveWellVisits"),
    "/kushalaya/enquiries": t("nav.items.liveWellEnquiries"),
    "/kushalaya/vendors": t("nav.items.liveWellVendors"),
    "/kushalaya/targets": t("nav.items.liveWellTargets"),
    "/kushalaya/room-checks": t("nav.items.liveWellRoomChecks"),
    "/kushalaya/hiring": t("nav.items.liveWellHiring"),
    "/kushalaya/blog": t("nav.items.liveWellBlog"),
    "/kushalaya/owner": t("nav.items.liveWellOwner"),
    "/kushalaya/invoices": t("nav.items.liveWellInvoices"),
    "/kushalaya/catalog": t("nav.items.liveWellCatalog"),
    "/kushalaya/coupons": t("nav.items.liveWellCoupons"),
    "/kushalaya/iot-devices": t("nav.items.liveWellIotDevices"),
    "/kushalaya/rubric": t("nav.items.liveWellChecklist"),
    "/kushalaya/activity": t("nav.items.liveWellActivity"),
    "/users": t("nav.items.liveWellTeam"),
    "/settings": t("nav.items.settings"),
  };
  return map[n] || n;
}

function pickItem(href: string, t: TranslateFn): NavItem {
  return {
    href,
    label: labelForHref(href, t),
  };
}

function stripElderCareNoise(groups: NavGroup[]): NavGroup[] {
  return groups
    .map((g) => ({
      ...g,
      items: g.items.filter((item) => {
        const href = normalizeLiveWellHref(item.href);
        if (ELDER_ONLY_HREFS.has(item.href) || ELDER_ONLY_HREFS.has(href)) return false;
        if (item.href.startsWith("/monitoring") || href.startsWith("/monitoring")) return false;
        if (item.href.startsWith("/cleaning") || href.startsWith("/cleaning")) return false;
        return true;
      }),
    }))
    .filter((g) => g.items.length > 0);
}

/**
 * Rebuild the core items into the ops menu above. Every Kushalaya route is
 * listed explicitly, so routes the core JSON lists but the owner did not
 * approve (solutions, pricing, ...) simply do not appear.
 */
function regroupLiveWellNav(groups: NavGroup[], t: TranslateFn): NavGroup[] {
  const hasDashboard = groups.some((g) => g.items.some((i) => i.href === "/dashboard"));
  const section = (titleKey: string, hrefs: readonly string[]): NavGroup => ({
    title: t(titleKey),
    items: hrefs
      .filter((h) => h !== "/dashboard" || hasDashboard)
      .filter((h) => !HIDDEN_HREFS.has(h))
      .map((h) => pickItem(h, t)),
  });
  return [
    section(LIVEWELL_NAV_GROUP_KEYS.today, TODAY_HREFS),
    section(LIVEWELL_NAV_GROUP_KEYS.sales, SALES_HREFS),
    section(LIVEWELL_NAV_GROUP_KEYS.customers, CUSTOMER_HREFS),
    section(LIVEWELL_NAV_GROUP_KEYS.business, BUSINESS_HREFS),
    section(LIVEWELL_NAV_GROUP_KEYS.setup, SETUP_HREFS),
  ].filter((g) => g.items.length > 0);
}

/**
 * Role visibility for the ops sidebar, run after core appends its Admin group
 * (Team/Settings, already gated by role). The Admin items move into Setup as
 * Team · Wearables · Assessment questions · Settings.
 * - VIEWER: Today, Assessments, Customers
 * - CARE_MANAGER: Today, Sales, Customers, Team, Hiring, Settings
 * - TENANT_ADMIN / SYSTEM_ADMIN: everything
 */
export function filterNavGroupsForLiveWellRole(
  groups: NavGroup[],
  role: string,
  t?: TranslateFn,
): NavGroup[] {
  const isViewer = isViewerRole(role || "");
  const isFullAdmin = isAdmin(role || "");
  const tr: TranslateFn = t ?? ((k: string) => k);
  const setupTitle = tr(LIVEWELL_NAV_GROUP_KEYS.setup);

  const isAdminGroup = (g: NavGroup) =>
    g.items.some((i) => i.href === "/users" || i.href === "/settings" || i.href.startsWith("/settings/"));

  const adminItems = groups.filter(isAdminGroup).flatMap((g) => g.items);
  const team = adminItems.find((i) => i.href === "/users");
  const settings = adminItems.find((i) => i.href === "/settings");
  const otherAdmin = adminItems.filter((i) => i.href !== "/users" && i.href !== "/settings");

  const out: NavGroup[] = [];
  let sawSetup = false;
  for (const g of groups) {
    if (isAdminGroup(g)) continue;
    if (isViewer && g.title === setupTitle) continue;
    let items = g.items.filter((i) => {
      const href = normalizeLiveWellHref(i.href);
      if (isViewer && VIEWER_HIDDEN_HREFS.has(href)) return false;
      return isFullAdmin || !ADMIN_ONLY_HREFS.has(href);
    });
    if (g.title === setupTitle) {
      sawSetup = true;
      items = [
        ...(team ? [{ ...team, label: labelForHref("/users", tr) }] : []),
        ...items,
        ...(settings ? [settings] : []),
        ...otherAdmin,
      ];
    }
    if (items.length) out.push({ ...g, items });
  }
  if (!sawSetup && !isViewer) {
    const items = [
      ...(team ? [{ ...team, label: labelForHref("/users", tr) }] : []),
      ...(settings ? [settings] : []),
      ...otherAdmin,
    ];
    if (items.length) out.push({ title: setupTitle, items });
  }
  return out;
}

/**
 * LiveWell360-locked nav. Shared /opt/workforceos-core without LIVEWELL360 used to fall
 * back to ELDER_CARE layout — strip those routes and keep LiveWell paths.
 */
export function buildAdminNavGroups(
  t: TranslateFn,
  vertical: string,
  market?: string | null,
): NavGroup[] {
  const v = LIVEWELL_VERTICALS.has(vertical) ? "LIVEWELL360" : vertical;
  let groups = coreBuildAdminNavGroups(t, v, market);

  if (LIVEWELL_VERTICALS.has(vertical) || LIVEWELL_VERTICALS.has(v)) {
    const layout = verticalNavLayout(v);
    if (layout === "elder_care" || layout === "workforce_only") {
      groups = stripElderCareNoise(groups);
    }
    groups = regroupLiveWellNav(groups, t);
  }

  return groups;
}
