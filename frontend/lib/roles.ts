/**
 * One place for "what can this ops user see". Every role only sees what it can
 * use; route guards and backend checks stay as a silent safety net.
 *
 *   admin   TENANT_ADMIN / SYSTEM_ADMIN: everything
 *   manager CARE_MANAGER: day-to-day work, no business set-up pages
 *   viewer  VIEWER: Today + Care, read-only (the backend refuses its writes)
 */
import { getStoredAuth } from "./api";
import { canManageUsers, canWrite } from "./auth";

/** Pages only admins can open (menu, links, tiles and cards hide them for others). */
export const ADMIN_ONLY_PATHS = [
  "/kushalaya/owner",
  "/kushalaya/invoices",
  "/kushalaya/catalog",
  "/kushalaya/coupons",
  "/kushalaya/iot-devices",
  "/kushalaya/rubric",
  "/kushalaya/blog",
  "/settings/business",
  "/settings/privacy",
  "/settings/security",
] as const;

/** Pages a read-only VIEWER may not open (staff activity is not theirs to see). */
export const NO_VIEWER_PATHS = ["/kushalaya/activity"] as const;

export type Feature =
  /** admin-only pages and actions (business set-up, products, coupons, wearables, master data) */
  | "admin"
  /** any change: add, edit, schedule, reply, raise, upload */
  | "edit"
  /** Growth menu, Team and Settings */
  | "manage";

type Who = string | { role?: string | null } | null | undefined;

function roleOf(who?: Who): string {
  if (typeof who === "string") return who.toUpperCase();
  const u = who === undefined ? getStoredAuth() : who;
  return (u?.role || "").toUpperCase();
}

export function isAdmin(who?: Who): boolean {
  return canManageUsers(roleOf(who));
}

export function isViewer(who?: Who): boolean {
  return roleOf(who) === "VIEWER";
}

export function can(feature: Feature, who?: Who): boolean {
  const r = roleOf(who);
  if (feature === "admin") return canManageUsers(r);
  if (feature === "edit") return canWrite(r);
  return canWrite(r);
}

/** True when this user may open `href` (strips query/hash). */
export function canOpen(href: string, who?: Who): boolean {
  const path = href.split(/[?#]/)[0].replace(/\/+$/, "");
  const adminOnly = ADMIN_ONLY_PATHS.some((p) => path === p || path.startsWith(`${p}/`));
  if (adminOnly && !isAdmin(who)) return false;
  const noViewer = NO_VIEWER_PATHS.some((p) => path === p || path.startsWith(`${p}/`));
  return !(noViewer && isViewer(who));
}
