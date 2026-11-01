import type { AssessmentCategory, HomeSafetyAssessment, ItemRating } from "./assessment";
import { categoryCompletion, categoryScore } from "./assessment";
import { getApplicableCategories, categoriesForAssessment } from "./conditional";
import type { ResidentProfile } from "./resident-profile";

export type AssessmentStep =
  | { kind: "intake"; label: "Resident profile" }
  | { kind: "section"; categoryId: string; label: string; sectionNumber?: number }
  | { kind: "photos"; label: "Photos" }
  | { kind: "review"; label: "Review & save" };

export function photosStepIndex(steps: AssessmentStep[]): number {
  const i = steps.findIndex((s) => s.kind === "photos");
  return i >= 0 ? i : Math.max(0, steps.length - 2);
}

export function reviewStepIndex(steps: AssessmentStep[]): number {
  return Math.max(0, steps.length - 1);
}

/** Short label for wizard step chips (phone + iPad). */
export function stepShortLabel(step: AssessmentStep): string {
  switch (step.kind) {
    case "intake":
      return "Profile";
    case "photos":
      return "Photos";
    case "review":
      return "Review";
    case "section":
      if (step.sectionNumber != null) return `S${step.sectionNumber}`;
      return step.label.length > 10 ? `${step.label.slice(0, 9)}…` : step.label;
    default: {
      const _unreachable: never = step;
      return _unreachable;
    }
  }
}

export function buildAssessmentSteps(
  categories: AssessmentCategory[],
  profile: ResidentProfile,
): AssessmentStep[] {
  const applicable = getApplicableCategories(categories, profile);
  return [
    { kind: "intake", label: "Resident profile" },
    ...applicable.map((cat) => ({
      kind: "section" as const,
      categoryId: cat.id,
      label: cat.title,
      sectionNumber: cat.sectionNumber,
    })),
    { kind: "photos", label: "Photos" },
    { kind: "review", label: "Review & save" },
  ];
}

export function isCategoryComplete(
  category: AssessmentCategory,
  ratings: Record<string, ItemRating>,
): boolean {
  return categoryCompletion(category, ratings).percent === 100;
}

export function stepSummary(
  step: AssessmentStep,
  assessment: HomeSafetyAssessment,
  categories: AssessmentCategory[],
  profile: ResidentProfile,
): string {
  if (step.kind === "intake") {
    const name = [assessment.clientFirstName, assessment.clientLastName]
      .filter(Boolean)
      .join(" ");
    return name ? `${name}${profile.residentAge ? ` · ${profile.residentAge}y` : ""}` : "Not started";
  }
  if (step.kind === "section") {
    const cat = getApplicableCategories(categoriesForAssessment(categories, assessment), profile, assessment.ratings).find((c) => c.id === step.categoryId);
    if (!cat) return "";
    const { answered, total } = categoryCompletion(cat, assessment.ratings);
    const pts = Math.round(categoryScore(cat, assessment.ratings, profile));
    return `${answered}/${total} rated · ${pts}/${cat.maxPoints} pts`;
  }
  if (step.kind === "photos") {
    return `${assessment.photos.length} photo${assessment.photos.length === 1 ? "" : "s"}`;
  }
  return "Final score & report";
}
