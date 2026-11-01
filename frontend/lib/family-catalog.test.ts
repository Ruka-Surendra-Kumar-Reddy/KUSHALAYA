import { describe, expect, it } from "vitest";
import { familyPriceLabel, matchesSearch, shelfFor, shelvesWithItems } from "./family-catalog";
import type { FamilyProduct } from "./family-money";

const item = (over: Partial<FamilyProduct>): FamilyProduct => ({
  id: 1, product_code: "BTH-001", name: "Fixed grab bar", category: "Bathroom Safety",
  description: "Steel bar beside the toilet", kind: "product", unit: "", included: "", image_url: null,
  price_paise: 120000, price_with_gst_paise: 141600,
  recommended: false, reasons: [], ...over,
});

describe("family catalog", () => {
  it("puts every ops category on a named shelf", () => {
    const cats: [string, string][] = [
      ["Bathroom Safety", "safety"], ["Bedroom", "safety"], ["Living Room", "safety"],
      ["Entry & Exterior", "safety"], ["Hallway Safety", "safety"], ["Kitchen Safety", "safety"],
      ["Balcony Safety", "safety"], ["Mobility", "mobility"], ["Smart Home", "alerts"],
      ["Emergency Safety", "alerts"], ["Wearable", "alerts"], ["Health Monitoring", "health"],
      ["Kushalaya Services", "care"], ["Care & Wellness Services", "care"], ["Service", "care"],
      ["Nursing", "clinical"], ["Physiotherapy", "clinical"], ["Doctor & Diagnostics", "clinical"],
      ["Home Maintenance", "maintenance"], ["Property Management", "maintenance"],
      ["Transportation", "transport"],
    ];
    for (const [c, shelf] of cats) expect(shelfFor(c), c).toBe(shelf);
    expect(shelfFor("Something new")).toBe("other");
  });

  it("shows a selling price or 'Price on request', never anything else", () => {
    expect(familyPriceLabel({ price_with_gst_paise: 365800, unit: "" })).toBe("₹3,658 incl. GST");
    expect(familyPriceLabel({ price_with_gst_paise: 118000, unit: "per visit" })).toBe("₹1,180 incl. GST · per visit");
    expect(familyPriceLabel({ price_with_gst_paise: 0, unit: "" })).toBe("We'll quote after a visit");
  });

  it("searches name, description, category and code", () => {
    const p = item({});
    expect(matchesSearch(p, "grab")).toBe(true);
    expect(matchesSearch(p, "toilet bar")).toBe(true);
    expect(matchesSearch(p, "bth-001")).toBe(true);
    expect(matchesSearch(p, "nurse")).toBe(false);
    expect(matchesSearch(p, "  ")).toBe(true);
  });

  it("lists only shelves that have items, in order", () => {
    const shelves = shelvesWithItems([item({ category: "Nursing" }), item({ category: "Bathroom" })]);
    expect(shelves.map((s) => s.id)).toEqual(["safety", "clinical"]);
  });
});
