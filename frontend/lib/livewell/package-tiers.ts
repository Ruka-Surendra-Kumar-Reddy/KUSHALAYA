/**
 * Package tier → solution scope for quotes and AI concepts.
 * Matches backend progressive fallback when spreadsheet package_solutions is empty.
 */

import type { ImprovementPlan } from "./improvement-plan";
import type { ProductQuoteDraft } from "./product-recommendations";

export const ACTIVE_TIERS = ["essential", "comfort", "premium"] as const;
export type AIPackageLevel = (typeof ACTIVE_TIERS)[number];
export type PackageTierScope = AIPackageLevel;

export const TIER_LABELS: Record<string, string> = {
  essential: "Essential",
  comfort: "Comfort",
  premium: "Premium",
};

/** Highest selected tier wins (premium ⊃ comfort ⊃ essential). */
export function getPackageTierScope(tiers: string[]): PackageTierScope {
  const selected = new Set(tiers.map((t) => t.trim().toLowerCase()).filter(Boolean));
  if (selected.has("premium")) return "premium";
  if (selected.has("comfort")) return "comfort";
  return "essential";
}

/** Progressive slice of ordered solution IDs for a package tier. */
export function solutionIdsForPackageTiers(
  orderedSolutionIds: string[],
  tiers: string[],
): string[] {
  const ordered = [...new Set(orderedSolutionIds.filter(Boolean))];
  const n = ordered.length;
  if (!n) return [];
  if (!tiers.length) return ordered;

  const scope = getPackageTierScope(tiers);
  if (scope === "essential") return ordered.slice(0, Math.max(1, Math.floor(n / 3)));
  if (scope === "comfort") return ordered.slice(0, Math.max(1, Math.floor((2 * n) / 3)));
  return ordered;
}

export function filterImprovementPlanBySolutionIds(
  plan: ImprovementPlan,
  solutionIds: string[],
): ImprovementPlan {
  const allowed = new Set(solutionIds);
  return {
    ...plan,
    entries: plan.entries.filter((e) => allowed.has(e.solution.id)),
  };
}

export function filterProductQuoteDraftBySolutionIds(
  draft: ProductQuoteDraft,
  solutionIds: string[],
): ProductQuoteDraft {
  const allowed = new Set(solutionIds);
  const items = draft.items.filter((item) =>
    item.solutionIds.some((id) => allowed.has(id)),
  );
  const priced = items.filter((i) => i.lineTotalInr != null);
  const subtotalInr = priced.length
    ? priced.reduce((sum, i) => sum + (i.lineTotalInr ?? 0), 0)
    : null;
  const unmappedSolutions = draft.unmappedSolutions.filter((s) => allowed.has(s.id));

  return {
    items,
    subtotalInr,
    pricedItemCount: priced.length,
    unmappedSolutions,
  };
}

/** Build tier-scoped plan + product draft for the customer quote. */
export function scopeQuoteToPackageTiers(
  plan: ImprovementPlan,
  draft: ProductQuoteDraft,
  tiers: string[],
): {
  plan: ImprovementPlan;
  draft: ProductQuoteDraft;
  scope: PackageTierScope;
  solutionIds: string[];
} {
  const orderedIds = plan.entries.map((e) => e.solution.id);
  const solutionIds = solutionIdsForPackageTiers(orderedIds, tiers);
  return {
    plan: filterImprovementPlanBySolutionIds(plan, solutionIds),
    draft: filterProductQuoteDraftBySolutionIds(draft, solutionIds),
    scope: getPackageTierScope(tiers),
    solutionIds,
  };
}
