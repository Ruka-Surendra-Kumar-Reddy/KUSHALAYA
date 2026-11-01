import { describe, expect, it } from "vitest";

import {
  catalogProductGroupKey,
  groupCatalogProductsByPrefix,
  nextProductCode,
  resolveCatalogCategoryTypes,
} from "./catalog";
import type { CatalogProduct } from "./catalog-types";

function product(overrides: Partial<CatalogProduct> = {}): CatalogProduct {
  return {
    id: "prod_test",
    name: "Test product",
    short_description: "",
    details: "",
    category: "General",
    price_label: "Quote",
    sort_order: 1,
    ...overrides,
  };
}

describe("groupCatalogProductsByPrefix", () => {
  it("shows products grouped by spreadsheet category when prefix is non-standard", () => {
    const products = [
      product({ id: "p1", name: "Grab bars", category: "Modification", category_prefix: "Modification" }),
      product({ id: "p2", name: "Assessment", category: "Assessment", category_prefix: "Assessment" }),
    ];

    const groups = groupCatalogProductsByPrefix(products);
    expect(groups).toHaveLength(2);
    expect(groups.map((g) => g.prefix).sort()).toEqual(["Assessment", "Modification"]);
    expect(groups.find((g) => g.prefix === "Modification")?.products).toHaveLength(1);
  });

  it("falls back to category when category_prefix is missing", () => {
    const key = catalogProductGroupKey(
      product({ category: "Smart Home", category_prefix: undefined }),
    );
    expect(key).toBe("Smart Home");
  });

  it("uses standard prefix when set", () => {
    const key = catalogProductGroupKey(
      product({ category: "Ignored", category_prefix: "BTH" }),
    );
    expect(key).toBe("BTH");
  });

  it("respects an admin type order", () => {
    const products = [
      product({ id: "p1", name: "Grab bar", category_prefix: "BTH" }),
      product({ id: "p2", name: "Visit", category_prefix: "SVC" }),
    ];
    const groups = groupCatalogProductsByPrefix(products, ["SVC", "BTH"]);
    expect(groups.map((g) => g.prefix)).toEqual(["SVC", "BTH"]);
  });
});

describe("nextProductCode", () => {
  it("increments the highest numeric SKU for a prefix", () => {
    expect(
      nextProductCode("SVC", [
        product({ id: "a", product_code: "SVC-005" }),
        product({ id: "b", product_code: "SVC-014" }),
        product({ id: "c", product_code: "WEL-009" }),
      ]),
    ).toBe("SVC-015");
  });
});

describe("resolveCatalogCategoryTypes", () => {
  it("seeds factory types when none are stored", () => {
    const types = resolveCatalogCategoryTypes({ products: [], packages: [] });
    expect(types.some((t) => t.prefix === "SVC" && t.kind === "service")).toBe(true);
    expect(types.some((t) => t.prefix === "BTH" && t.kind === "product")).toBe(true);
  });
});
