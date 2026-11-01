/**
 * Ops pages retired in the 2026-10 clean-up: the multi-partner network,
 * suppliers, solution library (suggestions now live inside assessments and
 * visits), price lists, master data, AI jobs, prospects and multi-agency
 * tenants. The code stays, but nothing links to these pages
 * and middleware sends direct visits to the dashboard. Don't build on them.
 */
export const RETIRED_OPS_PATHS = [
  "/kushalaya/partners",
  "/kushalaya/suppliers",
  "/kushalaya/solutions",
  "/kushalaya/pricing",
  "/kushalaya/master-data",
  "/kushalaya/ai-jobs",
  "/home-safety/partners",
  "/home-safety/suppliers",
  "/home-safety/solutions",
  "/home-safety/pricing",
  "/home-safety/master-data",
  "/home-safety/ai-jobs",
  "/settings/workflows",
  "/settings/subscription",
  "/settings/background-jobs",
  "/prospects",
  "/tenants",
  "/documents",
] as const;

export function isRetiredOpsPath(pathname: string): boolean {
  return RETIRED_OPS_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

/**
 * Pages that stay in use but are not menu items. Session activity is linked
 * from Settings. (Alerts and Assessments came back to the menu in FIX 110.)
 */
export const MENU_HIDDEN_PATHS = ["/kushalaya/activity"] as const;
