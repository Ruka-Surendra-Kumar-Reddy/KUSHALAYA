import { describe, expect, it } from "vitest";
import type { AssessmentCategory } from "./assessment";
import { completionPercent, normalizedScore } from "./assessment";
import { categoriesForAssessment } from "./conditional";
import { EMPTY_RESIDENT_PROFILE } from "./resident-profile";

// Same case as backend tests/test_rubric_gap_fixes.py::test_tiny_rubric_parity_case.
const cats: AssessmentCategory[] = [
  {
    id: "technology",
    title: "Tech",
    maxPoints: 2,
    items: [
      { id: "technology_can_use_phone_for_emergencies", label: "Phone", maxPoints: 1 },
      { id: "technology_home_secure_locks_visitor_check", label: "Secure", maxPoints: 1 },
    ],
  },
];
const ratings = { technology_can_use_phone_for_emergencies: "excellent" as const };
const score = (a: { status: string; createdAt: string; completedAt?: string | null }) =>
  normalizedScore(categoriesForAssessment(cats, { ...a, ratings }), ratings, EMPTY_RESIDENT_PROFILE);

describe("questions added after an assessment", () => {
  it("leaves an unanswered new question out of an old completed assessment", () => {
    expect(score({ status: "completed", createdAt: "2026-10-01" })).toBe(100);
    const scoped = categoriesForAssessment(cats, { status: "completed", createdAt: "2026-10-01", ratings });
    expect(completionPercent(scoped, ratings, EMPTY_RESIDENT_PROFILE)).toBe(100);
  });

  it("counts the new question on new assessments and on drafts", () => {
    expect(score({ status: "completed", createdAt: "2026-10-11" })).toBe(50);
    expect(score({ status: "draft", createdAt: "2026-10-01", completedAt: null })).toBe(50);
  });

  it("keeps an answered new question on an old completed assessment", () => {
    const answered = { ...ratings, technology_home_secure_locks_visitor_check: "unsafe" as const };
    const scoped = categoriesForAssessment(cats, { status: "completed", createdAt: "2026-10-01", ratings: answered });
    expect(normalizedScore(scoped, answered, EMPTY_RESIDENT_PROFILE)).toBe(50);
  });
});
