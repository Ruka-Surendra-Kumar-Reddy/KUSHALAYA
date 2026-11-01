import { describe, expect, it } from "vitest";
import { verticalContract, verticalFeatures, verticalHasFeature } from "@workforceos/contracts";
import { verticalFeatures as appVerticalFeatures } from "./features";

describe("workforceos-core contract", () => {
  it("matches @workforceos/contracts elder care pack", () => {
    expect(verticalHasFeature("ELDER_CARE", "care_plans")).toBe(true);
    expect(verticalHasFeature("HOUSEKEEPING", "elders")).toBe(false);
    expect(verticalContract.defaultVertical).toBe("ELDER_CARE");
    expect(verticalHasFeature("LIVEWELL360", "livewell")).toBe(true);
  });

  it("app features.ts delegates to core package", () => {
    const core = verticalFeatures("ELDER_CARE");
    const app = appVerticalFeatures("ELDER_CARE");
    expect([...app].sort()).toEqual([...core].sort());
  });
});
