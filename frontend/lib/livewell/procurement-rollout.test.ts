import { describe, expect, it } from "vitest";

import { DEFAULT_SAFETY_CATALOG } from "./catalog-defaults";
import { createEmptyAssessment } from "./assessment";
import { DEFAULT_SAFETY_CATEGORIES } from "./rubric-defaults";
import { DEFAULT_SOLUTION_LIBRARY } from "./solution-defaults";
import { buildImprovementPlan } from "./improvement-plan";
import { buildProductRecommendations } from "./product-recommendations";
import { buildPurchaseOrder, purchaseOrderCostTotalInr } from "./build-purchase-order";
import { DEFAULT_SUPPLIER_DIRECTORY } from "./supplier-defaults";
import {
  directoryToWorkbookBundle,
  parseSuppliersCsv,
  suppliersToCsv,
  workbookBundleToDirectory,
} from "./supplier-workbook";
import { DEFAULT_SAFEHOME_PRICING } from "./pricing-defaults";
import { buildSafeHomeQuote, computeVendorProductTotalInr } from "./pricing-engine";

describe("build-purchase-order", () => {
  it("auto-selects vendor per quote line", () => {
    const assessment = createEmptyAssessment();
    assessment.ratings.home_safety_toilet_grab_bar_installed = "unsafe";
    const plan = buildImprovementPlan(
      assessment,
      DEFAULT_SAFETY_CATEGORIES,
      DEFAULT_SOLUTION_LIBRARY,
    );
    const draft = buildProductRecommendations(plan, DEFAULT_SAFETY_CATALOG);
    const po = buildPurchaseOrder(assessment.id, draft, DEFAULT_SUPPLIER_DIRECTORY, {
      quantity: 1,
    });
    expect(po.lines.length).toBeGreaterThan(0);
    expect(po.lines[0].product_id).toBeTruthy();
    expect(po.lines[0].supplier_name).toBeTruthy();
  });
});

describe("supplier-workbook", () => {
  it("round-trips directory through workbook bundle", () => {
    const bundle = directoryToWorkbookBundle(DEFAULT_SUPPLIER_DIRECTORY);
    const restored = workbookBundleToDirectory(bundle);
    expect(restored.suppliers.length).toBe(DEFAULT_SUPPLIER_DIRECTORY.suppliers.length);
    expect(restored.offers.length).toBe(DEFAULT_SUPPLIER_DIRECTORY.offers.length);
  });

  it("parses suppliers csv", () => {
    const csv = suppliersToCsv(directoryToWorkbookBundle(DEFAULT_SUPPLIER_DIRECTORY).Suppliers);
    const rows = parseSuppliersCsv(csv);
    expect(rows[0].SupplierID).toBe("sup_ageasy");
  });
});

describe("vendor-cost margin", () => {
  it("computes vendor product total and optional margin basis", () => {
    const assessment = createEmptyAssessment();
    assessment.ratings.home_safety_toilet_grab_bar_installed = "unsafe";
    const plan = buildImprovementPlan(
      assessment,
      DEFAULT_SAFETY_CATEGORIES,
      DEFAULT_SOLUTION_LIBRARY,
    );
    const draft = buildProductRecommendations(plan, DEFAULT_SAFETY_CATALOG);
    const vendorTotal = computeVendorProductTotalInr(draft, DEFAULT_SUPPLIER_DIRECTORY);
    expect(vendorTotal).toBeGreaterThan(0);

    const quoteSell = buildSafeHomeQuote(draft, plan, DEFAULT_SAFEHOME_PRICING, {}, {
      suppliers: DEFAULT_SUPPLIER_DIRECTORY,
    })!;
    expect(quoteSell.productTotalInr).toBeGreaterThan(vendorTotal);

    const quoteVendorMargin = buildSafeHomeQuote(
      draft,
      plan,
      { ...DEFAULT_SAFEHOME_PRICING, use_vendor_cost_for_margin: true },
      {},
      { suppliers: DEFAULT_SUPPLIER_DIRECTORY },
    )!;
    expect(quoteVendorMargin.vendorProductCostInr).toBe(vendorTotal);
    expect(quoteVendorMargin.grandTotalInr).toBeGreaterThan(0);
  });
});
