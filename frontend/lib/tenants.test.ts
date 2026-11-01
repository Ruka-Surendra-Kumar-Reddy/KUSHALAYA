import { describe, expect, it } from "vitest";

import { tenantVerticalId } from "./tenants";

describe("tenantVerticalId", () => {
  it("normalizes casing and unknown values", () => {
    expect(tenantVerticalId({ vertical: "elder_care" })).toBe("ELDER_CARE");
    expect(tenantVerticalId({ vertical: "ELDER_CARE" })).toBe("ELDER_CARE");
  });
});
