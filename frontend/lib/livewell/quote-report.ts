import type { AssessmentCategory, HomeSafetyAssessment } from "./assessment";
import type { SafetyCatalog } from "./catalog-types";
import { buildImprovementPlan, type ImprovementPlan } from "./improvement-plan";
import { buildSafeHomeQuote, formatSafeHomeQuoteText } from "./pricing-engine";
import type { QuoteInputs, SafeHomePricingConfig } from "./pricing-types";
import {
  buildProductRecommendations,
  formatProductQuoteDraftText,
  type ProductQuoteDraft,
} from "./product-recommendations";
import {
  buildPackageCostComparisons,
  formatPackageComparisonsText,
} from "./package-savings";
import { scopeQuoteToPackageTiers } from "./package-tiers";
import type { SolutionLibrary } from "./solution-types";
import { withPublicBrand } from "@/lib/public-brand";

export function hasQuoteableFindings(
  assessment: HomeSafetyAssessment,
  categories: AssessmentCategory[],
  library: SolutionLibrary,
): boolean {
  const plan = buildImprovementPlan(assessment, categories, library);
  return plan.entries.length > 0;
}

export function buildQuoteReportText(
  assessment: HomeSafetyAssessment,
  categories: AssessmentCategory[],
  library: SolutionLibrary,
  catalog: SafetyCatalog,
  pricing: SafeHomePricingConfig,
  inputs: QuoteInputs = {},
  options?: {
    packageTiers?: string[];
    draft?: ProductQuoteDraft;
    plan?: ImprovementPlan;
  },
): string | null {
  const fullPlan = buildImprovementPlan(assessment, categories, library);
  if (!fullPlan.entries.length) return null;

  const fullDraft = buildProductRecommendations(fullPlan, catalog);
  if (!fullDraft.items.length && !options?.draft?.items.length) {
    return [
      "QUOTE ESTIMATE (partial assessment)",
      "",
      "Solutions matched, but no catalog products are linked yet.",
      "",
      // Customer-facing: solution codes (LW-…) are internal ids, list findings only.
      ...fullPlan.entries.map((e) => e.solution.finding),
    ].join("\n");
  }

  const tiers = options?.packageTiers ?? ["essential", "comfort", "premium"];
  const scoped = scopeQuoteToPackageTiers(fullPlan, fullDraft, tiers);
  const plan = options?.plan ?? scoped.plan;
  const draft = options?.draft ?? scoped.draft;

  if (!draft.items.length) {
    return [
      "QUOTE ESTIMATE (partial assessment)",
      "",
      tiers.length
        ? `No catalog products in package tier scope (${tiers.join(", ")}).`
        : "No package tier selected.",
      "",
      ...plan.entries.map((e) => e.solution.finding),
    ].join("\n");
  }

  const quote = buildSafeHomeQuote(draft, plan, pricing, inputs);
  const packageText = formatPackageComparisonsText(
    buildPackageCostComparisons(catalog, draft),
  );
  const parts = [
    withPublicBrand("QUOTE ESTIMATE (partial assessment — not a finalized LiveWell360 report)"),
    "",
    `Package tiers: ${tiers.join(", ") || "none"}`,
    "",
    formatProductQuoteDraftText(draft),
  ];
  if (quote) parts.push(formatSafeHomeQuoteText(quote, draft));
  parts.push(packageText);
  return parts.join("\n\n");
}
