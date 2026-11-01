import { describe, expect, it } from "vitest";

import { evaluateConditionalRule, RULE } from "./conditional-rules";
import { EMPTY_RESIDENT_PROFILE, type ResidentProfile } from "./resident-profile";

const profile = (overrides: Partial<ResidentProfile> = {}): ResidentProfile => ({
  ...EMPTY_RESIDENT_PROFILE,
  ...overrides,
});

describe("evaluateConditionalRule", () => {
  it("skips stairs items when home has no stairs", () => {
    expect(evaluateConditionalRule("unless_has_stairs", profile({ hasStairs: false }))).toBe(true);
    expect(evaluateConditionalRule("unless_has_stairs", profile({ hasStairs: true }))).toBe(false);
  });

  it("wheelchair, lives alone, smart home, balcony, helpers", () => {
    expect(evaluateConditionalRule("unless_wheelchair_user", profile())).toBe(true);
    expect(
      evaluateConditionalRule("unless_wheelchair_user", profile({ mobilityDevice: "wheelchair" })),
    ).toBe(false);
    expect(evaluateConditionalRule("unless_lives_alone", profile({ livesAlone: true }))).toBe(false);
    expect(
      evaluateConditionalRule("unless_smart_home_advanced", profile({ smartHomeAdvanced: true })),
    ).toBe(false);
    expect(evaluateConditionalRule("unless_has_balcony", profile({ hasBalcony: true }))).toBe(false);
    expect(
      evaluateConditionalRule("unless_domestic_helper", profile({ domesticHelper: true })),
    ).toBe(false);
    expect(
      evaluateConditionalRule("unless_full_time_caregiver", profile({ fullTimeCaregiver: true })),
    ).toBe(false);
  });

  it("assistive device and ramp relevance", () => {
    expect(evaluateConditionalRule("unless_assistive_device", profile({ mobilityDevice: "none" }))).toBe(
      true,
    );
    expect(evaluateConditionalRule("unless_assistive_device", profile({ mobilityDevice: "cane" }))).toBe(
      false,
    );
    expect(evaluateConditionalRule("unless_ramp_relevant", profile({ hasStairs: true }))).toBe(false);
    expect(
      evaluateConditionalRule("unless_ramp_relevant", profile({ mobilityDevice: "wheelchair" })),
    ).toBe(false);
    expect(evaluateConditionalRule("unless_ramp_relevant", profile())).toBe(true);
  });

  it("named RULE map exists for rubric skipWhen", () => {
    expect(RULE.STAIRS).toEqual({ when: "unless_has_stairs" });
    expect(RULE.NO_SMART_HOME).toEqual({ field: "smartHomeAssessment", equals: false });
  });
});
