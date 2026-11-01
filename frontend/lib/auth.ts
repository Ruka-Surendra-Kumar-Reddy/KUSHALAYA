import {
  STAFF_ROLES,
  canManageUsers,
  canWrite,
  isStaffRole,
  isSuperAdmin,
} from "@workforceos/contracts/client";

import type { AuthUser } from "./api";
import { getStoredAuth } from "./api";

export { STAFF_ROLES, canManageUsers, canWrite, isStaffRole, isSuperAdmin };

export function isCaregiverRole(role: string) {
  return role === "CAREGIVER";
}

export function isElderPortalRole(role: string) {
  return role === "ELDER_PORTAL";
}

/** Default landing route after login for each role */
export function homePathForRole(role: string): string {
  if (isElderPortalRole(role)) return "/kushalaya/family/dashboard";
  if (isCaregiverRole(role)) return "/caregiver";
  if (isStaffRole(role)) return "/dashboard";
  return "/login";
}

/** Settings page (language, bench cost); tenant branding remains admin-only. */
export function canAccessSettings(role: string) {
  return canManageUsers(role) || role === "CARE_MANAGER";
}

export function canManageTenantBranding(role: string) {
  return canManageUsers(role);
}

/** View agency team directory (no invite). */
export function canViewTeam(role: string) {
  return canAccessSettings(role);
}

export function canManageMonitoringConfig(role: string) {
  return canWrite(role);
}

export function canManageTenants(role: string) {
  return isSuperAdmin(role);
}

/** Super admin without an impersonated tenant — tenant-scoped APIs will 400. */
export function platformAdminNeedsTenantContext(
  auth: AuthUser | null | undefined,
): boolean {
  return Boolean(auth && canManageTenants(auth.role) && auth.tenant_id == null);
}

export function roleLabel(role: string) {
  if (role === "SYSTEM_ADMIN") return "Super admin";
  if (role === "TENANT_ADMIN") return "Tenant admin";
  if (role === "CARE_MANAGER") return "Care manager";
  if (role === "ELDER_PORTAL") return "Family portal";
  if (role === "CAREGIVER") return "Caregiver";
  return role;
}

export function canVerifyDocuments(role: string) {
  return canManageUsers(role) || role === "CARE_MANAGER";
}

export function requireAuth(): AuthUser | null {
  return getStoredAuth();
}
