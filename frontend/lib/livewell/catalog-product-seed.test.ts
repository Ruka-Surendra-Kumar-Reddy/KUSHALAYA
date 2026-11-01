import { describe, expect, it } from "vitest";

import { DEFAULT_SAFETY_CATALOG } from "./catalog-defaults";
import { productsForSolution, SEEDED_CATALOG_PRODUCTS } from "./catalog-product-seed";
import { DEFAULT_SOLUTION_LIBRARY } from "./solution-defaults";

describe("catalog product seed", () => {
  it("ships LiveWell catalog SKUs mirrored from the master workbook", () => {
    expect(SEEDED_CATALOG_PRODUCTS.length).toBeGreaterThan(50);
    expect(DEFAULT_SAFETY_CATALOG.products.length).toBe(SEEDED_CATALOG_PRODUCTS.length);
    expect(SEEDED_CATALOG_PRODUCTS.some((p) => p.product_code === "SMT-006")).toBe(true);
  });

  it("assigns unique product codes", () => {
    const codes = SEEDED_CATALOG_PRODUCTS.map((p) => p.product_code).filter(Boolean);
    expect(new Set(codes).size).toBe(codes.length);
  });

  it("links grab-bar solution to bathroom grab bar SKU", () => {
    const matches = productsForSolution(SEEDED_CATALOG_PRODUCTS, "LW-HS-BTH-001");
    expect(matches.some((p) => p.product_code === "BTH-001")).toBe(true);
  });

  it("only references valid solution library ids", () => {
    const valid = new Set(DEFAULT_SOLUTION_LIBRARY.solutions.map((s) => s.id));
    for (const product of SEEDED_CATALOG_PRODUCTS) {
      for (const sid of product.solution_ids ?? []) {
        expect(valid.has(sid), `${product.product_code} → ${sid}`).toBe(true);
      }
    }
  });
});
