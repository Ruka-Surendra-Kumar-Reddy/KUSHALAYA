import { describe, expect, it } from "vitest";

import type { AssessmentCategory, HomeSafetyAssessment } from "./assessment";
import {
  buildAssessmentSteps,
  photosStepIndex,
  reviewStepIndex,
  stepShortLabel,
  stepSummary,
  type AssessmentStep,
} from "./assessFlow";
import { EMPTY_RESIDENT_PROFILE } from "./resident-profile";

const categories: AssessmentCategory[] = [
  {
    id: "bath",
    title: "Bathroom Safety Extra",
    maxPoints: 4,
    sectionNumber: 2,
    items: [{ id: "b1", label: "Grab bar", maxPoints: 4 }],
  },
];

describe("assessFlow helpers", () => {
  it("builds intake, sections, photos, review", () => {
    const steps = buildAssessmentSteps(categories, EMPTY_RESIDENT_PROFILE);
    expect(steps[0]).toEqual({ kind: "intake", label: "Resident profile" });
    expect(steps.at(-2)?.kind).toBe("photos");
    expect(steps.at(-1)?.kind).toBe("review");
    expect(photosStepIndex(steps)).toBe(steps.length - 2);
    expect(reviewStepIndex(steps)).toBe(steps.length - 1);
  });

  it("short labels", () => {
    expect(stepShortLabel({ kind: "intake", label: "Resident profile" })).toBe("Profile");
    expect(stepShortLabel({ kind: "photos", label: "Photos" })).toBe("Photos");
    expect(stepShortLabel({ kind: "review", label: "Review & save" })).toBe("Review");
    expect(
      stepShortLabel({
        kind: "section",
        categoryId: "bath",
        label: "Bathroom Safety Extra",
        sectionNumber: 2,
      }),
    ).toBe("S2");
    expect(
      stepShortLabel({
        kind: "section",
        categoryId: "bath",
        label: "Bathroom Safety Extra",
      }),
    ).toBe("Bathroom …");
  });

  it("summarizes intake and photos", () => {
    const steps = buildAssessmentSteps(categories, {
      ...EMPTY_RESIDENT_PROFILE,
      residentAge: "78",
    });
    const assessment = {
      clientFirstName: "Lakshmi",
      clientLastName: "Rao",
      ratings: {},
      photos: [{ id: "p1" }, { id: "p2" }],
    } as unknown as HomeSafetyAssessment;
    expect(stepSummary(steps[0], assessment, categories, { ...EMPTY_RESIDENT_PROFILE, residentAge: "78" })).toContain(
      "Lakshmi Rao",
    );
    const photoStep = steps.find((s) => s.kind === "photos") as AssessmentStep;
    expect(stepSummary(photoStep, assessment, categories, EMPTY_RESIDENT_PROFILE)).toBe("2 photos");
  });

  it("photos fallback index when missing", () => {
    const steps: AssessmentStep[] = [
      { kind: "intake", label: "Resident profile" },
      { kind: "review", label: "Review & save" },
    ];
    expect(photosStepIndex(steps)).toBe(0);
  });
});
