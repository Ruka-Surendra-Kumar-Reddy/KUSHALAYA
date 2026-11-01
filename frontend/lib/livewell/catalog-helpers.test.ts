import { describe, expect, it } from "vitest";

import {
  catalogPriceIncludesInstallLabor,
  formatInr,
  nextProductCode,
  parseInstalledPriceRange,
  productUnitPriceInr,
  productsForPackage,
} from "./catalog";
import type { CatalogProduct, SafetyCatalog } from "./catalog-types";

const product = (overrides: Partial<CatalogProduct> = {}): CatalogProduct => ({
  id: "p1",
  name: "Grab bar",
  short_description: "",
  details: "",
  category: "Bathroom Safety",
  price_inr: 1200,
  price_label: "Installed",
  sort_order: 0,
  ...overrides,
});

describe("catalog pricing helpers", () => {
  it("nextProductCode increments padded sku", () => {
    expect(nextProductCode("BTH", [])).toBe("BTH-001");
    expect(
      nextProductCode("BTH", [product({ product_code: "BTH-7" }), product({ product_code: "BTH-012" })]),
    ).toBe("BTH-013");
  });

  it("parseInstalledPriceRange midpoint", () => {
    expect(parseInstalledPriceRange("₹1,200–₹1,800")).toBe(1500);
    expect(parseInstalledPriceRange("no prices")).toBeNull();
    expect(parseInstalledPriceRange("₹2,000")).toBe(2000);
  });

  it("productUnitPriceInr prefers numeric then ranges", () => {
    expect(productUnitPriceInr(product({ price_inr: 500 }))).toBe(500);
    expect(productUnitPriceInr(product({ price_inr: 0, installed_price: "₹1,000–₹3,000" }))).toBe(
      2000,
    );
    expect(
      productUnitPriceInr(product({ price_inr: null, installed_price: "", product_cost: "₹800" })),
    ).toBe(800);
    expect(productUnitPriceInr(product({ price_inr: null, installed_price: "", product_cost: "" }))).toBeNull();
  });

  it.each([
    ["Installed grab bar", true],
    ["Product + labor", true],
    ["product + labour", true],
    ["Per visit", false],
    ["Per hour", false],
    ["Setup fee", false],
    ["", false],
    ["Retail", false],
  ] as const)("catalogPriceIncludesInstallLabor %s", (label, expected) => {
    expect(catalogPriceIncludesInstallLabor(product({ price_label: label }))).toBe(expected);
  });

  it("formatInr", () => {
    expect(formatInr(null, "")).toBe("Quote on visit");
    expect(formatInr(null, "Ask")).toBe("Ask");
    expect(formatInr(1500, "From")).toMatch(/From/);
  });

  it("productsForPackage maps ids", () => {
    const catalog: SafetyCatalog = {
      products: [product({ id: "a" }), product({ id: "b" })],
      packages: [
        {
          id: "pkg",
          name: "Kit",
          tagline: "",
          description: "",
          price_inr: 1,
          price_label: "",
          highlight: false,
          product_ids: ["b", "missing"],
          sort_order: 0,
        },
      ],
    };
    expect(productsForPackage(catalog, catalog.packages[0]).map((p) => p.id)).toEqual(["b"]);
  });
});
