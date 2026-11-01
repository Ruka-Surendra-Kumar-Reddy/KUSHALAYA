import { describe, expect, it } from "vitest";

import { createEmptyAssessment } from "./assessment";
import { DEFAULT_SAFETY_CATALOG } from "./catalog-defaults";
import { buildImprovementPlan } from "./improvement-plan";
import { DEFAULT_SAFEHOME_PRICING } from "./pricing-defaults";
import {
  buildSafeHomeQuote,
  estimateLaborHours,
  formatSafeHomeQuoteText,
  parseInstallationHours,
} from "./pricing-engine";
import { buildProductRecommendations } from "./product-recommendations";
import { DEFAULT_SAFETY_CATEGORIES } from "./rubric-defaults";
import { DEFAULT_SOLUTION_LIBRARY } from "./solution-defaults";

describe("pricing engine", () => {
  it("parses installation time strings", () => {
    expect(parseInstallationHours("2 hours")).toBe(2);
    expect(parseInstallationHours("1–2 hours")).toBe(1.5);
    expect(parseInstallationHours("")).toBeNull();
  });

  it("builds quote with margin and GST", () => {
    const assessment = createEmptyAssessment();
    assessment.ratings.home_safety_toilet_grab_bar_installed = "unsafe";

    const plan = buildImprovementPlan(
      assessment,
      DEFAULT_SAFETY_CATEGORIES,
      DEFAULT_SOLUTION_LIBRARY,
    );
    const draft = buildProductRecommendations(plan, DEFAULT_SAFETY_CATALOG);
    const quote = buildSafeHomeQuote(draft, plan, DEFAULT_SAFEHOME_PRICING)!;

    expect(quote.productTotalInr).toBeGreaterThan(0);
    // Grab-bar SKUs are priced installed (product + labor) — engine must not double-count labor.
    expect(quote.laborHours).toBe(0);
    expect(quote.marginAmountInr).toBeGreaterThan(0);
    expect(quote.gstAmountInr).toBeGreaterThan(0);
    expect(quote.grandTotalInr).toBeGreaterThan(quote.productTotalInr);
    expect(quote.grandTotalInr % 100).toBe(0);
  });

  it("applies minimum service charge when labor is small", () => {
    const assessment = createEmptyAssessment();
    assessment.ratings.home_safety_toilet_grab_bar_installed = "unsafe";
    const plan = buildImprovementPlan(
      assessment,
      DEFAULT_SAFETY_CATEGORIES,
      DEFAULT_SOLUTION_LIBRARY,
    );
    const draft = buildProductRecommendations(plan, DEFAULT_SAFETY_CATALOG);
    const config = {
      ...DEFAULT_SAFEHOME_PRICING,
      labor_rate_per_hour_inr: 50,
      default_labor_hours_per_solution: 1,
      minimum_service_charge_inr: 500,
    };
    const quote = buildSafeHomeQuote(draft, plan, config, { labor_hours: 1 })!;
    expect(quote.serviceMinimumApplied).toBe(true);
    expect(quote.laborTotalInr).toBeGreaterThanOrEqual(500);
  });

  it("formats quote text with grand total", () => {
    const assessment = createEmptyAssessment();
    assessment.ratings.home_safety_toilet_grab_bar_installed = "unsafe";
    const plan = buildImprovementPlan(
      assessment,
      DEFAULT_SAFETY_CATEGORIES,
      DEFAULT_SOLUTION_LIBRARY,
    );
    const draft = buildProductRecommendations(plan, DEFAULT_SAFETY_CATALOG);
    const quote = buildSafeHomeQuote(draft, plan, DEFAULT_SAFEHOME_PRICING)!;
    const text = formatSafeHomeQuoteText(quote, draft);
    expect(text).toContain("GRAND TOTAL");
    expect(text).toContain("GST");
  });

  it("skips estimated labor when catalog prices already include install", () => {
    const assessment = createEmptyAssessment();
    assessment.ratings.home_safety_toilet_grab_bar_installed = "unsafe";
    const plan = buildImprovementPlan(
      assessment,
      DEFAULT_SAFETY_CATEGORIES,
      DEFAULT_SOLUTION_LIBRARY,
    );
    const draft = buildProductRecommendations(plan, DEFAULT_SAFETY_CATALOG);
    expect(draft.items.length).toBeGreaterThan(0);
    expect(
      draft.items.every((i) =>
        (i.product.price_label || "").toLowerCase().includes("installed"),
      ),
    ).toBe(true);
    const hours = estimateLaborHours(plan, draft, DEFAULT_SAFEHOME_PRICING);
    expect(hours).toBe(0);
  });
});
