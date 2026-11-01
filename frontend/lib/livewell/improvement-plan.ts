import type {
  AssessmentCategory,
  HomeSafetyAssessment,
  ItemRating,
  SafeHomeRating,
} from "./assessment";
import { normalizeRating, normalizedScore, ratingLabel, projectedSafetyAge, safetyAge } from "./assessment";
import { EMPTY_RESIDENT_PROFILE, parseResidentAge } from "./resident-profile";
import type { ResidentProfile } from "./resident-profile";
import { getApplicableCategories, categoriesForAssessment } from "./conditional";
import type { SafeHomeSolution, SolutionLibrary, SolutionPriority } from "./solution-types";
import { SOLUTION_PRIORITY_ORDER } from "./solution-types";

export interface ImprovementPlanFinding {
  itemId: string;
  itemLabel: string;
  categoryTitle: string;
  rating: SafeHomeRating;
  note?: string;
}

export interface ImprovementPlanEntry {
  solution: SafeHomeSolution;
  findings: ImprovementPlanFinding[];
}

export interface ImprovementPlan {
  entries: ImprovementPlanEntry[];
  byPriority: Record<SolutionPriority, ImprovementPlanEntry[]>;
  currentScore: number;
  projectedScore: number;
  totalScoreGain: number;
  findingCount: number;
}

function isFindingRating(rating: ItemRating | undefined): boolean {
  const r = normalizeRating(rating);
  return r === "unsafe" || r === "acceptable";
}

export function buildImprovementPlan(
  assessment: HomeSafetyAssessment,
  categories: AssessmentCategory[],
  library: SolutionLibrary,
  profile: ResidentProfile = assessment.residentProfile ?? EMPTY_RESIDENT_PROFILE,
): ImprovementPlan {
  categories = categoriesForAssessment(categories, assessment);
  const safeProfile = profile ?? EMPTY_RESIDENT_PROFILE;
  const ratings = assessment.ratings ?? {};
  const itemNotes = assessment.itemNotes ?? {};
  const applicable = getApplicableCategories(categories ?? [], safeProfile, ratings);
  const itemMeta = new Map<
    string,
    { label: string; categoryTitle: string; rating: SafeHomeRating; note?: string }
  >();

  for (const cat of applicable) {
    for (const item of cat.items) {
      const rating = normalizeRating(ratings[item.id]);
      if (!isFindingRating(ratings[item.id])) continue;
      itemMeta.set(item.id, {
        label: item.label,
        categoryTitle: cat.title,
        rating,
        note: itemNotes[item.id]?.trim() || undefined,
      });
    }
  }

  const entryMap = new Map<string, ImprovementPlanEntry>();

  for (const solution of library?.solutions ?? []) {
    const matchedFindings: ImprovementPlanFinding[] = [];
    for (const itemId of solution.rubricItemIds ?? []) {
      const meta = itemMeta.get(itemId);
      if (!meta) continue;
      matchedFindings.push({
        itemId,
        itemLabel: meta.label,
        categoryTitle: meta.categoryTitle,
        rating: meta.rating,
        note: meta.note,
      });
    }
    if (!matchedFindings.length) continue;
    entryMap.set(solution.id, { solution, findings: matchedFindings });
  }

  const priorityRank = (p: SolutionPriority) => SOLUTION_PRIORITY_ORDER.indexOf(p);

  const entries = [...entryMap.values()].sort(
    (a, b) =>
      priorityRank(a.solution.priority) - priorityRank(b.solution.priority) ||
      b.solution.scoreImprovement - a.solution.scoreImprovement,
  );

  const byPriority = SOLUTION_PRIORITY_ORDER.reduce(
    (acc, p) => {
      acc[p] = entries.filter((e) => e.solution.priority === p);
      return acc;
    },
    {} as Record<SolutionPriority, ImprovementPlanEntry[]>,
  );

  const currentScore = normalizedScore(categories ?? [], ratings, safeProfile);
  const projectedScore = realisticProjection(currentScore, entries);
  const totalScoreGain = projectedScore - currentScore;

  return {
    entries,
    byPriority,
    currentScore,
    projectedScore,
    totalScoreGain,
    findingCount: itemMeta.size,
  };
}

/** Most any one area (bathroom, stairs…) can add, however many fixes it has. */
export const AREA_GAIN_CAP = 10;
/** Fixes never close more than this share of the gap to 100. */
export const MAX_GAP_CLOSED = 0.8;

/**
 * "After fixes" score. Summing every solution's gain jumped straight to 100, so:
 * within an area the biggest fix counts fully and each next one half as much
 * (fixes overlap), each area is capped, and the result closes at most 80% of
 * the remaining gap.
 */
export function realisticProjection(currentScore: number, entries: ImprovementPlanEntry[]): number {
  const byArea = new Map<string, number[]>();
  for (const e of entries) {
    const area = e.solution.section || e.findings[0]?.categoryTitle || "Other";
    const gains = byArea.get(area) ?? [];
    gains.push(Math.max(0, Number(e.solution.scoreImprovement) || 0));
    byArea.set(area, gains);
  }
  let total = 0;
  for (const gains of byArea.values()) {
    gains.sort((a, b) => b - a);
    const area = gains.reduce((sum, g, i) => sum + g * Math.pow(0.5, i), 0);
    total += Math.min(AREA_GAIN_CAP, area);
  }
  const gap = Math.max(0, 100 - currentScore);
  return Math.round(currentScore + Math.min(total, gap * MAX_GAP_CLOSED));
}

export function formatImprovementPlanText(plan: ImprovementPlan): string {
  if (!plan.entries.length) {
    return "No automated improvement items — all rated items are Excellent or N/A.";
  }

  const lines: string[] = [
    "IMPROVEMENT PLAN (LiveWell360 Solution Library v1)",
    `Current score: ${plan.currentScore} → Projected: ${plan.projectedScore} (+${plan.totalScoreGain} est.)`,
    `Findings driving plan: ${plan.findingCount}`,
    "",
  ];

  for (const priority of SOLUTION_PRIORITY_ORDER) {
    const group = plan.byPriority[priority];
    if (!group.length) continue;
    lines.push(`${priority.toUpperCase()} (${group.length})`);
    for (const entry of group) {
      const s = entry.solution;
      const title = s.name || s.finding;
      const evidence = s.evidenceLevel ? ` · Evidence ${s.evidenceLevel}` : "";
      // Customer-facing text: solution codes (LW-…) are internal ids, keep them out.
      lines.push(`  ${title}${evidence}`);
      if (s.subcategory) lines.push(`    Category: ${s.section} / ${s.subcategory}`);
      if (s.riskDescription) lines.push(`    Why: ${s.riskDescription}`);
      if (s.recommendedSolutions?.length) {
        lines.push(`    Actions: ${s.recommendedSolutions.join("; ")}`);
      }
      if (s.productCategories?.length) {
        lines.push(`    Products: ${s.productCategories.join(", ")}`);
      }
      if (s.contractorType) lines.push(`    Professional: ${s.contractorType}`);
      if (s.estimatedCost) lines.push(`    Cost: ${s.estimatedCost}`);
      if (s.installationTime) lines.push(`    Time: ${s.installationTime}`);
      if (s.followUpDays) lines.push(`    Follow-up: ${s.followUpDays} days`);
      lines.push(`    Score gain: +${s.scoreImprovement}`);
      for (const f of entry.findings) {
        lines.push(`    From: ${f.itemLabel} (${ratingLabel(f.rating)})`);
      }
      lines.push("");
    }
  }

  return lines.join("\n").trim();
}

export function safetyAgeProjection(
  assessment: HomeSafetyAssessment,
  plan: ImprovementPlan,
): { current: number | null; projected: number | null } {
  const age = parseResidentAge(assessment.residentProfile ?? EMPTY_RESIDENT_PROFILE);
  if (age == null) return { current: null, projected: null };
  return {
    current: safetyAge(age, plan.currentScore),
    projected: projectedSafetyAge(age, plan.currentScore, plan.projectedScore - plan.currentScore),
  };
}
