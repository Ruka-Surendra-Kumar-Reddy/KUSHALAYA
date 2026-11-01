import { describe, expect, it } from "vitest";

import { bandClass, bandLabel, normalizeEnrollment } from "./academy";

describe("bandLabel", () => {
  it.each([
    ["GOLD", "Gold — Deployable"],
    ["SILVER", "Silver — Minor training"],
    ["BRONZE", "Bronze — Training needed"],
    ["NOT_READY", "Not ready"],
    ["", "Not ready"],
  ] as const)("%s", (band, label) => {
    expect(bandLabel(band)).toBe(label);
  });
});

describe("bandClass", () => {
  it.each([
    ["GOLD", "badge badge-low"],
    ["gold", "badge badge-low"],
    ["SILVER", "badge badge-medium"],
    ["BRONZE", "badge badge-high"],
    ["x", "badge"],
  ] as const)("%s", (band, cls) => {
    expect(bandClass(band)).toBe(cls);
  });
});

describe("normalizeEnrollment", () => {
  it("uppercases code and status", () => {
    expect(
      normalizeEnrollment({
        id: 1,
        program_id: 2,
        program_code: "qp-eld",
        program_name: "Elder care",
        status: "enrolled",
        assessment_score: 80,
      }),
    ).toMatchObject({ program_code: "QP-ELD", status: "ENROLLED" });
  });
});
