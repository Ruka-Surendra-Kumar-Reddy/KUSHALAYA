import { describe, expect, it } from "vitest";

import { createEmptyAssessment } from "./assessment";
import { DEFAULT_SAFETY_CATALOG } from "./catalog-defaults";
import { buildImprovementPlan } from "./improvement-plan";
import {
  buildProductRecommendations,
  formatProductQuoteDraftText,
} from "./product-recommendations";
import { DEFAULT_SAFETY_CATEGORIES } from "./rubric-defaults";
import { DEFAULT_SOLUTION_LIBRARY } from "./solution-defaults";

describe("product recommendations", () => {
  it("maps improvement plan solutions to catalog SKUs", () => {
    const assessment = createEmptyAssessment();
    assessment.ratings.home_safety_toilet_grab_bar_installed = "unsafe";

    const plan = buildImprovementPlan(
      assessment,
      DEFAULT_SAFETY_CATEGORIES,
      DEFAULT_SOLUTION_LIBRARY,
    );
    const draft = buildProductRecommendations(plan, DEFAULT_SAFETY_CATALOG);

    expect(draft.items.some((i) => i.product.product_code === "BTH-001")).toBe(true);
    expect(draft.items.find((i) => i.product.product_code === "BTH-001")?.solutionIds).toContain(
      "LW-HS-BTH-001",
    );
    expect(draft.subtotalInr).toBeGreaterThan(0);
  });

  it("dedupes products triggered by multiple solutions", () => {
    const assessment = createEmptyAssessment();
    assessment.ratings.home_safety_toilet_grab_bar_installed = "unsafe";
    assessment.ratings.home_safety_shower_grab_bar_installed = "unsafe";

    const plan = buildImprovementPlan(
      assessment,
      DEFAULT_SAFETY_CATEGORIES,
      DEFAULT_SOLUTION_LIBRARY,
    );
    const draft = buildProductRecommendations(plan, DEFAULT_SAFETY_CATALOG);
    const grabBars = draft.items.filter((i) => i.product.product_code === "BTH-001");

    expect(grabBars.length).toBe(1);
    expect(grabBars[0]?.solutionIds.length).toBeGreaterThanOrEqual(2);
  });

  it("returns empty items when plan has no entries", () => {
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
    const draft = buildProductRecommendations(plan, DEFAULT_SAFETY_CATALOG);

    expect(draft.items.length).toBe(0);
    expect(draft.subtotalInr).toBeNull();
  });

  it("formats quote draft text with subtotal", () => {
    const assessment = createEmptyAssessment();
    assessment.ratings.home_safety_toilet_grab_bar_installed = "unsafe";
    const plan = buildImprovementPlan(
      assessment,
      DEFAULT_SAFETY_CATEGORIES,
      DEFAULT_SOLUTION_LIBRARY,
    );
    const draft = buildProductRecommendations(plan, DEFAULT_SAFETY_CATALOG);
    const text = formatProductQuoteDraftText(draft);

    expect(text).toContain("BTH-001");
    expect(text).toContain("Subtotal");
  });
});
