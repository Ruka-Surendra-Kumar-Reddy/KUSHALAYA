import { describe, expect, it } from "vitest";

import {
  formatPurchaseOrderText,
  purchaseOrderCostTotalInr,
  purchaseOrderLineKey,
  purchaseOrderToCsv,
  quoteDraftLineKey,
} from "./build-purchase-order";
import type { ProductQuoteDraft } from "./product-recommendations";
import type { SafeHomePurchaseOrder } from "./procurement-types";

const order: SafeHomePurchaseOrder = {
  id: "po-1",
  assessment_id: "a1",
  status: "draft",
  job_city: "Hyderabad",
  notes: "Handle with care",
  created_at: "2026-01-01T00:00:00.000Z",
  updated_at: "2026-01-01T00:00:00.000Z",
  lines: [
    {
      product_id: "p1",
      product_code: "BTH-001",
      product_name: "Grab bar",
      quantity: 2,
      supplier_id: "s1",
      supplier_name: "Acme",
      supplier_cost_inr: 400,
      vendor_sku: "GB-1",
      lead_time_days: 3,
      moq: 1,
      selection_reason: "lowest cost",
      sell_unit_price_inr: 600,
    },
  ],
};

describe("purchase order helpers", () => {
  it("totals cost times quantity", () => {
    expect(purchaseOrderCostTotalInr(order)).toBe(800);
  });

  it("builds stable line keys", () => {
    expect(purchaseOrderLineKey(order)).toBe("p1:2");
    const draft = {
      items: [{ product: { id: "p1" }, quantity: 2 }],
    } as unknown as ProductQuoteDraft;
    expect(quoteDraftLineKey(draft)).toBe("p1:2");
  });

  it("formats text and csv", () => {
    const text = formatPurchaseOrderText(order);
    expect(text).toContain("PURCHASE ORDER");
    expect(text).toContain("BTH-001");
    expect(text).toContain("Hyderabad");
    expect(text).toContain("Handle with care");
    const csv = purchaseOrderToCsv(order);
    expect(csv.split("\n")[0]).toContain("ProductID");
    expect(csv).toContain("Grab bar");
    expect(csv).toContain("400");
  });

  it("csv-escapes commas and quotes", () => {
    const messy: SafeHomePurchaseOrder = {
      ...order,
      lines: [
        {
          ...order.lines[0],
          product_name: 'Bar, "steel"',
        },
      ],
    };
    expect(purchaseOrderToCsv(messy)).toContain('"Bar, ""steel"""');
  });
});
