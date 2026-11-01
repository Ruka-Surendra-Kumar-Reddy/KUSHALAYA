import { describe, expect, it } from "vitest";

import { formatFollowUp, stageLabel } from "./prospects";

describe("stageLabel", () => {
  it.each([
    ["NEW", "NEW"],
    ["ASSESSMENT_DONE", "ASSESSMENT DONE"],
    ["DOCS_PENDING", "DOCS PENDING"],
    ["a_b_c", "a b c"],
  ] as const)("%s", (stage, label) => {
    expect(stageLabel(stage)).toBe(label);
  });
});

describe("formatFollowUp", () => {
  it("returns em dash for empty", () => {
    expect(formatFollowUp(null)).toBe("—");
  });

  it("marks past dates overdue", () => {
    const text = formatFollowUp("2000-01-01T00:00:00.000Z");
    expect(text).toContain("(overdue)");
  });

  it("does not mark future dates overdue", () => {
    const text = formatFollowUp("2099-01-01T00:00:00.000Z");
    expect(text).not.toContain("(overdue)");
  });
});
