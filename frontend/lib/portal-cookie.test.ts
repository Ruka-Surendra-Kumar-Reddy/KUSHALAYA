import { describe, expect, it } from "vitest";

import { portalKindForRole } from "./portal-cookie";

describe("portal routing cookie", () => {
  it("maps roles to the portal the middleware should route to", () => {
    expect(portalKindForRole("ELDER_PORTAL")).toBe("family");
    expect(portalKindForRole("CAREGIVER")).toBe("caregiver");
    for (const role of ["SYSTEM_ADMIN", "TENANT_ADMIN", "CARE_MANAGER", "VIEWER"]) {
      expect(portalKindForRole(role)).toBe("staff");
    }
  });
});
