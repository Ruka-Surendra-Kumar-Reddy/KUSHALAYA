import { describe, expect, it } from "vitest";

import {
  canAccessSettings,
  canManageMonitoringConfig,
  canManageTenantBranding,
  canManageTenants,
  canVerifyDocuments,
  canViewTeam,
  homePathForRole,
  isCaregiverRole,
  isElderPortalRole,
  platformAdminNeedsTenantContext,
  roleLabel,
} from "./auth";

const STAFF = ["SYSTEM_ADMIN", "TENANT_ADMIN", "CARE_MANAGER", "VIEWER"] as const;

describe("role predicates", () => {
  it("detects caregiver and family portal roles", () => {
    expect(isCaregiverRole("CAREGIVER")).toBe(true);
    expect(isCaregiverRole("CARE_MANAGER")).toBe(false);
    expect(isElderPortalRole("ELDER_PORTAL")).toBe(true);
    expect(isElderPortalRole("CUSTOMER_PORTAL")).toBe(false);
  });

  it.each([
    ["ELDER_PORTAL", "/kushalaya/family/dashboard"],
    ["CAREGIVER", "/caregiver"],
    ["CARE_MANAGER", "/dashboard"],
    ["TENANT_ADMIN", "/dashboard"],
    ["SYSTEM_ADMIN", "/dashboard"],
    ["VIEWER", "/dashboard"],
    ["UNKNOWN", "/login"],
    ["", "/login"],
  ] as const)("homePathForRole(%s)", (role, path) => {
    expect(homePathForRole(role)).toBe(path);
  });
});

describe("permission helpers", () => {
  it.each([
    ["SYSTEM_ADMIN", true],
    ["TENANT_ADMIN", true],
    ["CARE_MANAGER", true],
    ["VIEWER", false],
    ["CAREGIVER", false],
    ["ELDER_PORTAL", false],
  ] as const)("canAccessSettings %s", (role, expected) => {
    expect(canAccessSettings(role)).toBe(expected);
    expect(canViewTeam(role)).toBe(expected);
    expect(canVerifyDocuments(role)).toBe(expected);
  });

  it.each([
    ["SYSTEM_ADMIN", true],
    ["TENANT_ADMIN", true],
    ["CARE_MANAGER", false],
    ["VIEWER", false],
  ] as const)("canManageTenantBranding %s", (role, expected) => {
    expect(canManageTenantBranding(role)).toBe(expected);
  });

  it.each([
    ["SYSTEM_ADMIN", true],
    ["TENANT_ADMIN", true],
    ["CARE_MANAGER", true],
    ["VIEWER", false],
  ] as const)("canManageMonitoringConfig %s", (role, expected) => {
    expect(canManageMonitoringConfig(role)).toBe(expected);
  });

  it("only super admin manages tenants", () => {
    expect(canManageTenants("SYSTEM_ADMIN")).toBe(true);
    expect(canManageTenants("TENANT_ADMIN")).toBe(false);
    expect(canManageTenants("CARE_MANAGER")).toBe(false);
  });
});

describe("platformAdminNeedsTenantContext", () => {
  it("is true only for super admin without tenant", () => {
    expect(
      platformAdminNeedsTenantContext({
        role: "SYSTEM_ADMIN",
        tenant_id: null,
        email: "a@b.c",
        access_token: "t",
        refresh_token: "r",
      }),
    ).toBe(true);
    expect(
      platformAdminNeedsTenantContext({
        role: "SYSTEM_ADMIN",
        tenant_id: 1,
        email: "a@b.c",
        access_token: "t",
        refresh_token: "r",
      }),
    ).toBe(false);
    expect(
      platformAdminNeedsTenantContext({
        role: "TENANT_ADMIN",
        tenant_id: null,
        email: "a@b.c",
        access_token: "t",
        refresh_token: "r",
      }),
    ).toBe(false);
    expect(platformAdminNeedsTenantContext(null)).toBe(false);
    expect(platformAdminNeedsTenantContext(undefined)).toBe(false);
  });
});

describe("roleLabel", () => {
  it.each([
    ["SYSTEM_ADMIN", "Super admin"],
    ["TENANT_ADMIN", "Tenant admin"],
    ["CARE_MANAGER", "Care manager"],
    ["ELDER_PORTAL", "Family portal"],
    ["CAREGIVER", "Caregiver"],
    ["VIEWER", "VIEWER"],
    ["CUSTOM", "CUSTOM"],
  ] as const)("%s", (role, label) => {
    expect(roleLabel(role)).toBe(label);
  });

  it("staff roles used in tests remain defined", () => {
    expect(STAFF).toContain("VIEWER");
  });
});
