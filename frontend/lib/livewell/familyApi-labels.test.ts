import { describe, expect, it } from "vitest";

import { gradeStatus, planStatusLabel, priorityLabel } from "./familyApi";

describe("gradeStatus", () => {
  it.each([
    ["A", "excellent", "excellent"],
    ["B", "good", "good"],
    ["C", "", "moderate"],
    ["D", "", "high"],
    ["F", "", "critical"],
    ["platinum", "", "excellent"],
    ["gold", "", "good"],
    ["silver", "", "moderate"],
    ["bronze", "", "high"],
    ["red", "", "critical"],
    ["unknown", "", "moderate"],
    ["x", "CRITICAL", "critical"],
  ] as const)("grade=%s band=%s", (grade, band, expected) => {
    expect(gradeStatus(grade, band)).toBe(expected);
  });
});

describe("priority and plan labels", () => {
  it.each([
    ["critical", "Critical"],
    ["high", "High"],
    ["medium", "Medium"],
    ["low", "Low"],
    ["other", "other"],
  ] as const)("priority %s", (p, label) => {
    expect(priorityLabel(p)).toBe(label);
  });

  it.each([
    ["done", "Done"],
    ["scheduled", "Scheduled"],
    ["open", "Open"],
    ["unknown", "Open"],
  ] as const)("plan %s", (s, label) => {
    expect(planStatusLabel(s)).toBe(label);
  });
});
