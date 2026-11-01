import { describe, expect, it } from "vitest";

import type { SafetyCatalog } from "./catalog-types";
import {
  buildPackageCostComparisons,
  formatPackageComparisonsText,
  packagesForAssessorQuote,
} from "./package-savings";
import type { ProductQuoteDraft } from "./product-recommendations";

const catalog: SafetyCatalog = {
  products: [
    {
      id: "p1",
      name: "Grab bar",
      short_description: "",
      details: "",
      category: "Bath",
      price_inr: 3500,
      price_label: "From",
      sort_order: 1,
    },
    {
      id: "p2",
      name: "Night light",
      short_description: "",
      details: "",
      category: "Bed",
      price_inr: 1000,
      price_label: "From",
      sort_order: 2,
    },
    {
      id: "p3",
      name: "Sensor",
      short_description: "",
      details: "",
      category: "Smart",
      price_inr: 5000,
      price_label: "From",
      sort_order: 3,
    },
  ],
  packages: [
    {
      id: "pkg_basic",
      name: "Basic safety",
      tagline: "",
      description: "",
      price_inr: 4000,
      price_label: "From",
      highlight: true,
      product_ids: ["p1", "p2"],
      sort_order: 1,
    },
    {
      id: "pkg_no_price",
      name: "Unpriced",
      tagline: "",
      description: "",
      price_inr: null,
      price_label: "Quote",
      highlight: false,
      product_ids: ["p1"],
      sort_order: 2,
    },
  ],
};

function draftWith(ids: string[]): ProductQuoteDraft {
  const items = ids.map((id) => {
    const product = catalog.products.find((p) => p.id === id)!;
    return {
      product,
      solutionIds: ["sol"],
      solutionFindings: ["finding"],
      quantity: 1,
      unitPriceInr: product.price_inr,
      lineTotalInr: product.price_inr,
    };
  });
  return {
    items,
    subtotalInr: items.reduce((s, i) => s + (i.lineTotalInr ?? 0), 0),
    pricedItemCount: items.length,
    unmappedSolutions: [],
  };
}

describe("package-savings", () => {
  it("computes full-bundle and recommended savings", () => {
    const comparisons = buildPackageCostComparisons(catalog, draftWith(["p1", "p2", "p3"]));
    expect(comparisons).toHaveLength(1);
    const basic = comparisons[0];
    expect(basic.packagePriceInr).toBe(4000);
    expect(basic.fullBundleRetailInr).toBe(4500);
    expect(basic.savingsVsFullBundleInr).toBe(500);
    expect(basic.overlapItemCount).toBe(2);
    expect(basic.recommendedOverlapInr).toBe(4500);
    expect(basic.savingsVsRecommendedInr).toBe(500);
    expect(basic.uncoveredRecommendedProductIds).toEqual(["p3"]);
    expect(basic.coverageRatio).toBeCloseTo(2 / 3);
  });

  it("skips packages without a price", () => {
    const comparisons = buildPackageCostComparisons(catalog, draftWith(["p1"]));
    expect(comparisons.every((c) => c.package.id !== "pkg_no_price")).toBe(true);
  });

  it("formats assessor text with cost difference", () => {
    const text = formatPackageComparisonsText(
      buildPackageCostComparisons(catalog, draftWith(["p1", "p2"])),
    );
    expect(text).toContain("PACKAGE OPTIONS");
    expect(text).toContain("Basic safety");
    expect(text).toContain("customer saves");
  });

  it("packagesForAssessorQuote prefers overlapping packages", () => {
    const rows = packagesForAssessorQuote(
      buildPackageCostComparisons(catalog, draftWith(["p1"])),
    );
    expect(rows[0]?.package.id).toBe("pkg_basic");
    expect(rows[0]?.overlapItemCount).toBe(1);
  });
});
