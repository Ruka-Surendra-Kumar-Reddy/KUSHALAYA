import { describe, expect, it } from "vitest";

import { DEFAULT_SAFETY_CATEGORIES } from "./rubric-defaults";
import { DEFAULT_SOLUTION_LIBRARY } from "./solution-defaults";
import { buildImprovementPlan } from "./improvement-plan";
import { createEmptyAssessment, normalizeAssessment } from "./assessment";

describe("improvement plan", () => {
  it("matches solutions when items are unsafe", () => {
    const assessment = createEmptyAssessment();
    const grabBarId = "home_safety_toilet_grab_bar_installed";
    assessment.ratings[grabBarId] = "unsafe";

    const plan = buildImprovementPlan(
      assessment,
      DEFAULT_SAFETY_CATEGORIES,
      DEFAULT_SOLUTION_LIBRARY,
    );

    expect(plan.entries.some((e) => e.solution.id === "LW-HS-BTH-001")).toBe(true);
    expect(plan.projectedScore).toBeGreaterThan(plan.currentScore);
  });

  it("returns empty plan when all items excellent", () => {
    const assessment = createEmptyAssessment();
    for (const cat of DEFAULT_SAFETY_CATEGORIES) {
      for (const item of cat.items) {
        assessment.ratings[item.id] = "excellent";
      }
    }
    const plan = buildImprovementPlan(
      assessment,
      DEFAULT_SAFETY_CATEGORIES,
      DEFAULT_SOLUTION_LIBRARY,
    );
    expect(plan.entries.length).toBe(0);
  });

  it("does not throw when residentProfile / ratings are missing (iPad sync)", () => {
    const partial = normalizeAssessment({
      id: "hs-ipad",
      createdAt: "2026-01-01T00:00:00.000Z",
      updatedAt: "2026-01-01T00:00:00.000Z",
      completedAt: null,
      status: "draft",
      clientFirstName: "Rama",
      clientLastName: "Rao",
      clientAddress: null,
      clientPhone: "9000000000",
      assessorName: "Ada",
      notes: "",
    } as never);
    expect(partial.residentProfile).toBeTruthy();
    expect(Array.isArray(partial.residentProfile.medicalConditions)).toBe(true);
    expect(partial.clientAddress).toBe("");
    expect(() =>
      buildImprovementPlan(partial, DEFAULT_SAFETY_CATEGORIES, DEFAULT_SOLUTION_LIBRARY),
    ).not.toThrow();
  });
});
