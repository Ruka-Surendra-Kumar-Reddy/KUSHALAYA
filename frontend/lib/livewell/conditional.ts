import type { AssessmentCategory, AssessmentItem, SkipRule } from "./assessment";
import { evaluateConditionalRule } from "./conditional-rules";
import type { ResidentProfile } from "./resident-profile";
import { normalizeRating } from "./assessment";

export function matchesSkipRule(rule: SkipRule | undefined, profile: ResidentProfile): boolean {
  if (!rule) return false;
  if (rule.when) return evaluateConditionalRule(rule.when, profile);
  if (rule.field) {
    const value = profile[rule.field as keyof ResidentProfile];
    if (rule.equals !== undefined) return value === rule.equals;
    if (rule.notEquals !== undefined) return value !== rule.notEquals;
  }
  return false;
}

type RatingMap = Record<string, unknown> | null | undefined;

/**
 * Hidden questions stay in the bank but are not asked on new assessments.
 * An old assessment that already answered one keeps it, so its report still renders.
 */
export function isHiddenUnanswered(item: AssessmentItem, ratings?: RatingMap): boolean {
  if (!item.hidden) return false;
  return normalizeRating((ratings?.[item.id] ?? null) as never) == null;
}

/**
 * Questions added after assessments already existed (backend rubric_gap_fixes, 2026-10-11).
 * Same map as backend scoring.QUESTIONS_ADDED_ON. An item may also carry `addedOn`.
 */
export const QUESTIONS_ADDED_ON: Record<string, string> = {
  home_safety_bathroom_well_ventilated: "2026-10-11",
  health_wellness_bp_sugar_checked_regularly: "2026-10-11",
  cognitive_emotional_safe_from_wandering_getting_lost: "2026-10-11",
  technology_light_switches_easy_to_reach_and_operate: "2026-10-11",
  technology_home_secure_locks_visitor_check: "2026-10-11",
};

type AssessmentLike = {
  status?: string | null;
  completedAt?: string | null;
  createdAt?: string | null;
  ratings?: RatingMap;
};

/**
 * On a completed assessment, a question added after it was started and left unanswered
 * was never asked: mark it hidden so scores leave it out of earned points and section
 * totals (same as hidden-unanswered). Drafts are unchanged and still ask the new questions.
 * Mirrors backend scoring.categories_for_payload.
 */
export function categoriesForAssessment(
  categories: AssessmentCategory[],
  assessment: AssessmentLike | null | undefined,
): AssessmentCategory[] {
  if (!assessment) return categories;
  const completed = String(assessment.status ?? "").toLowerCase() === "completed" || Boolean(assessment.completedAt);
  if (!completed) return categories;
  const started = String(assessment.createdAt ?? "").slice(0, 10);
  const ratings = assessment.ratings;
  return categories.map((cat) => ({
    ...cat,
    items: cat.items.map((item) => {
      const added = item.addedOn || QUESTIONS_ADDED_ON[item.id] || "";
      if (!added || item.hidden || (started && started >= added)) return item;
      if (normalizeRating((ratings?.[item.id] ?? null) as never) != null) return item;
      return { ...item, hidden: true };
    }),
  }));
}

export function isItemApplicable(
  item: AssessmentItem,
  category: AssessmentCategory,
  profile: ResidentProfile,
  ratings?: RatingMap,
): boolean {
  if (isHiddenUnanswered(item, ratings)) return false;
  if (matchesSkipRule(category.skipWhen, profile)) return false;
  if (matchesSkipRule(item.skipWhen, profile)) return false;
  return true;
}

export function getApplicableCategories(
  categories: AssessmentCategory[],
  profile: ResidentProfile,
  ratings?: RatingMap,
): AssessmentCategory[] {
  return categories
    .filter((cat) => !matchesSkipRule(cat.skipWhen, profile))
    .map((cat) => ({
      ...cat,
      items: cat.items.filter((item) => isItemApplicable(item, cat, profile, ratings)),
    }))
    .filter((cat) => cat.items.length > 0);
}

export function getApplicableItems(
  categories: AssessmentCategory[],
  profile: ResidentProfile,
  ratings?: RatingMap,
): AssessmentItem[] {
  return getApplicableCategories(categories, profile, ratings).flatMap((c) => c.items);
}

export function countSkippedItems(
  categories: AssessmentCategory[],
  profile: ResidentProfile,
): number {
  let total = 0;
  let applicable = 0;
  for (const cat of categories) {
    if (matchesSkipRule(cat.skipWhen, profile)) {
      total += cat.items.filter((i) => !i.hidden).length;
      continue;
    }
    for (const item of cat.items) {
      if (item.hidden) continue;
      total += 1;
      if (isItemApplicable(item, cat, profile)) applicable += 1;
    }
  }
  return total - applicable;
}

export function isItemAnswered(
  itemId: string,
  ratings: Record<string, string | null | undefined>,
): boolean {
  const rating = normalizeRating(ratings[itemId] as never);
  return rating != null;
}
