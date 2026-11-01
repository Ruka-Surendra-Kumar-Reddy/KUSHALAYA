import { isStaffRole } from "@workforceos/contracts/client";

/**
 * Routing hint for the middleware — NOT an auth credential.
 *
 * The session lives in localStorage, which the server cannot see, so every
 * portal URL used to render "Loading…" and only bounce to /login once the JS
 * had downloaded and run (3–5s on a cold phone). This cookie tells the
 * middleware which portal the browser last signed in to, so `/` and the
 * portal pages redirect on the server instead. The client-side guards and the
 * API's token checks remain the real gate; a forged cookie only changes which
 * page you are redirected to.
 */
export const PORTAL_COOKIE = "ks_portal";

export type PortalKind = "staff" | "family" | "caregiver";

export function portalKindForRole(role: string): PortalKind {
  if (role === "ELDER_PORTAL") return "family";
  if (isStaffRole(role)) return "staff";
  return "caregiver";
}

const MAX_AGE_DAYS = 30;

function cookieAttrs(): string {
  const secure = typeof location !== "undefined" && location.protocol === "https:" ? "; Secure" : "";
  return `; Path=/; SameSite=Lax${secure}`;
}

export function setPortalCookie(role: string) {
  if (typeof document === "undefined") return;
  const kind = portalKindForRole(role);
  const current = readPortalCookie();
  if (current === kind) return;
  document.cookie = `${PORTAL_COOKIE}=${kind}; Max-Age=${MAX_AGE_DAYS * 86400}${cookieAttrs()}`;
}

export function clearPortalCookie() {
  if (typeof document === "undefined") return;
  document.cookie = `${PORTAL_COOKIE}=; Max-Age=0${cookieAttrs()}`;
}

export function readPortalCookie(): PortalKind | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(new RegExp(`(?:^|;\\s*)${PORTAL_COOKIE}=(staff|family|caregiver)`));
  return (m?.[1] as PortalKind | undefined) ?? null;
}
