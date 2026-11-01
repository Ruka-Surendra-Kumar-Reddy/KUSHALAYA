/**
 * Family portal paths, resolved per host.
 *
 * The same pages serve two hosts:
 *
 *   family.kushalaya.com/<path>   <- middleware rewrites to /kushalaya/family/<path>
 *   ops.kushalaya.com/kushalaya/family/<path>
 *
 * Middleware normalises `/kushalaya/family/*` back to the clean path on the
 * family host, but **only for real page loads**. Client-side navigations are
 * deliberately left alone (redirecting them breaks the router — see
 * `isRscFetch` in middleware.ts), so a `router.push("/kushalaya/family/login")`
 * on the family host puts `family.kushalaya.com/kushalaya/family/login` in the
 * address bar: the repeated-brand URL the owner asked us to get rid of.
 *
 * So client-side navigation must pick the path that matches the host it is on.
 * Hardcoding either form is a bug: on the ops host `/login` and `/dashboard`
 * are the STAFF pages, not the family ones.
 */

const FAMILY_PREFIX = "/kushalaya/family";

/** True when the current URL is the ops-host form, e.g. /kushalaya/family/x. */
function onOpsHostPath(): boolean {
  if (typeof window === "undefined") return true; // SSR: assume the full path
  return window.location.pathname.startsWith(FAMILY_PREFIX);
}

/** Family portal path for `suffix` ("/login", "/dashboard", …). */
export function familyPath(suffix: string): string {
  const clean = suffix.startsWith("/") ? suffix : `/${suffix}`;
  return onOpsHostPath() ? `${FAMILY_PREFIX}${clean}` : clean;
}

export const familyLoginPath = () => familyPath("/login");
export const familyDashboardPath = () => familyPath("/dashboard");
