/** Routes that require tenant context when logged in as SYSTEM_ADMIN without tenant_id. */

const TENANT_SCOPED_PREFIXES = [
  "/executive",
  "/prospects",
  "/matching",
  "/elders",
  "/assignments",
  "/monitoring",
  "/billing",
  "/communications",
  "/settings/workflows",
  "/settings/subscription",
  "/kushalaya/activity",
  "/copilot",
  "/cleaning",
];

export function platformAdminNeedsTenantForPath(
  pathname: string,
  searchParams?: URLSearchParams | string | null,
): boolean {
  if (pathname === "/workforce" || pathname.startsWith("/workforce/")) {
    const search =
      typeof searchParams === "string"
        ? searchParams
        : searchParams?.toString() ?? "";
    const tab = new URLSearchParams(
      search.startsWith("?") ? search.slice(1) : search,
    ).get("tab");
    return tab !== "marketplace";
  }

  for (const prefix of TENANT_SCOPED_PREFIXES) {
    if (pathname === prefix || pathname.startsWith(`${prefix}/`)) {
      return true;
    }
  }
  return false;
}

export function platformAdminGateFeatureLabel(pathname: string): string {
  if (pathname.startsWith("/executive")) return "Executive center";
  if (pathname.startsWith("/prospects")) return "Recruitment pipeline";
  if (pathname.startsWith("/matching")) return "Matching";
  if (pathname.startsWith("/elders")) return "Elders";
  if (pathname.startsWith("/assignments")) return "Assignments";
  if (pathname.startsWith("/monitoring")) return "Monitoring";
  if (pathname.startsWith("/billing")) return "Billing";
  if (pathname.startsWith("/communications")) return "Service requests";
  if (pathname.startsWith("/settings/workflows")) return "Workflow automation";
  if (pathname.startsWith("/kushalaya/activity")) return "Session activity";
  if (pathname.startsWith("/workforce")) return "Command center";
  if (pathname.startsWith("/cleaning")) return "Cleaning operations";
  return "this view";
}
