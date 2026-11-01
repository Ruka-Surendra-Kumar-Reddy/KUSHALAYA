import { describe, expect, it } from "vitest";

import { SEEDED_CATALOG_PRODUCTS } from "./catalog-product-seed";
import {
  draftFromQuoteLines,
  quoteLinesFromRecommended,
  recommendationFromProduct,
  rebuildProductQuoteDraft,
} from "./product-recommendations";

describe("editable quote draft helpers", () => {
  const product = SEEDED_CATALOG_PRODUCTS[0];

  it("builds a recommendation from a catalog product", () => {
    const line = recommendationFromProduct(product, 2);
    expect(line.product.id).toBe(product.id);
    expect(line.quantity).toBe(2);
    if (line.unitPriceInr != null) {
      expect(line.lineTotalInr).toBe(line.unitPriceInr * 2);
    }
  });

  it("filters draft to included lines only", () => {
    const base = rebuildProductQuoteDraft([
      recommendationFromProduct(product),
      recommendationFromProduct(SEEDED_CATALOG_PRODUCTS[1]),
    ]);
    const lines = quoteLinesFromRecommended(base);
    lines[0].included = false;
    const draft = draftFromQuoteLines(lines);
    expect(draft.items).toHaveLength(1);
    expect(draft.items[0].product.id).toBe(SEEDED_CATALOG_PRODUCTS[1].id);
  });
});
