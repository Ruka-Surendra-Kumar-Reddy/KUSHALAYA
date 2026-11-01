import { describe, expect, it } from "vitest";

import { DEFAULT_SUPPLIER_DIRECTORY } from "./supplier-defaults";
import { normalizeSupplierDirectory } from "./suppliers";
import { selectVendorOffer, supplierCostBasisInr } from "./supplier-selection";

describe("supplier-selection", () => {
  it("selects preferred vendor when eligible", () => {
    const selected = selectVendorOffer(DEFAULT_SUPPLIER_DIRECTORY, "prod_bth_001", {
      quantity: 5,
    });
    expect(selected?.supplier.id).toBe("sup_ageasy");
    expect(selected?.reason).toBe("preferred vendor");
  });

  it("falls back to lowest cost when preferred MOQ not met", () => {
    const selected = selectVendorOffer(DEFAULT_SUPPLIER_DIRECTORY, "prod_bth_001", {
      quantity: 1,
    });
    expect(selected?.supplier.id).toBe("sup_local_blr");
    expect(selected?.offer.supplier_cost_inr).toBe(820);
  });

  it("prefers city-matched vendor when job city set", () => {
    const selected = selectVendorOffer(DEFAULT_SUPPLIER_DIRECTORY, "prod_bth_001", {
      quantity: 1,
      jobCity: "Mumbai",
    });
    expect(selected?.supplier.city).toBe("Mumbai");
  });

  it("supplierCostBasisInr uses preferred when MOQ met", () => {
    expect(supplierCostBasisInr(DEFAULT_SUPPLIER_DIRECTORY, "prod_bth_001", 5)).toBe(850);
    expect(supplierCostBasisInr(DEFAULT_SUPPLIER_DIRECTORY, "prod_bth_001", 1)).toBe(820);
  });

  it("normalize keeps one preferred per product", () => {
    const out = normalizeSupplierDirectory({
      suppliers: [
        { id: "s1", name: "A", active: true, sort_order: 0, contact: "", phone: "", email: "", city: "", rating: null },
        { id: "s2", name: "B", active: true, sort_order: 1, contact: "", phone: "", email: "", city: "", rating: null },
      ],
      offers: [
        {
          id: "o1",
          product_id: "p1",
          supplier_id: "s1",
          supplier_cost_inr: 100,
          preferred: true,
          moq: 1,
          lead_time_days: 1,
          vendor_sku: "",
          active: true,
        },
        {
          id: "o2",
          product_id: "p1",
          supplier_id: "s2",
          supplier_cost_inr: 80,
          preferred: true,
          moq: 1,
          lead_time_days: 1,
          vendor_sku: "",
          active: true,
        },
      ],
    });
    const preferred = out.offers.filter((o) => o.preferred);
    expect(preferred).toHaveLength(1);
    expect(preferred[0].supplier_cost_inr).toBe(80);
  });
});
