import { describe, expect, it } from "vitest";

import { hasLegacyLaborCopy, withFactoryMarketingCopy, type CatalogProduct } from "./catalog";
import { DEFAULT_SAFETY_CATALOG } from "./catalog-defaults";

describe("withFactoryMarketingCopy", () => {
  it("replaces labor-only bathroom install copy from factory defaults", () => {
    const stale: CatalogProduct = {
      id: "prod_svc_002",
      product_code: "SVC-002",
      name: "Bathroom Safety Installation (labor)",
      short_description:
        "Partner installer labor for bathroom safety pack — products billed separately",
      details: "",
      category: "Services",
      category_prefix: "SVC",
      price_inr: 5000,
      price_label: "Labor (products extra)",
      sort_order: 2,
      image_ids: [99],
    };
    const next = withFactoryMarketingCopy({
      products: [stale],
      packages: [],
    });
    const fixed = next.products[0]!;
    expect(hasLegacyLaborCopy(stale)).toBe(true);
    expect(fixed.name).toBe(DEFAULT_SAFETY_CATALOG.products.find((p) => p.id === "prod_svc_002")?.name);
    expect(fixed.short_description).not.toMatch(/billed separately/i);
    expect(fixed.price_label).toMatch(/Installed/i);
    expect(fixed.image_ids).toEqual([99]);
  });

  it("keeps photos while refreshing package billed-separately copy", () => {
    const pkg = {
      ...DEFAULT_SAFETY_CATALOG.packages[0]!,
      description: "Products and partner installs billed separately. Best when score is good.",
    };
    const next = withFactoryMarketingCopy({
      products: [],
      packages: [pkg],
    });
    expect(next.packages[0]!.description).not.toMatch(/billed separately/i);
  });

  it("does not rewrite healthy package product lists from a parallel seed", () => {
    const pkg = {
      ...DEFAULT_SAFETY_CATALOG.packages[1]!,
      product_ids: ["prod_svc_001"],
      description: "Healthy description without labor-only wording.",
    };
    const next = withFactoryMarketingCopy({
      products: DEFAULT_SAFETY_CATALOG.products.slice(0, 3),
      packages: [pkg],
    });
    expect(next.packages[0]!.product_ids).toEqual(["prod_svc_001"]);
    expect(next.packages[0]!.description).toBe(pkg.description);
  });
});
