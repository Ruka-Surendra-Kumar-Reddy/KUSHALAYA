import { describe, expect, it } from "vitest";

import { EMPTY_RESIDENT_PROFILE, parseResidentAge } from "./resident-profile";

describe("parseResidentAge", () => {
  it.each([
    ["78", 78],
    ["0", null],
    ["-1", null],
    ["abc", null],
    [undefined, null],
  ] as const)("%j -> %s", (age, expected) => {
    expect(parseResidentAge({ ...EMPTY_RESIDENT_PROFILE, residentAge: age as string })).toBe(
      expected,
    );
  });
});

describe("EMPTY_RESIDENT_PROFILE", () => {
  it("enables smart home and balcony by default", () => {
    expect(EMPTY_RESIDENT_PROFILE.smartHomeAssessment).toBe(true);
    expect(EMPTY_RESIDENT_PROFILE.hasBalcony).toBe(true);
    expect(EMPTY_RESIDENT_PROFILE.medicalConditions).toEqual([]);
  });
});
