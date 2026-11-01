import { describe, expect, it } from "vitest";
import { aiPreviewHref, parseProductCodes, totalWithGst } from "./aiPreview";

describe("aiPreview", () => {
  it("builds the hazard-check 'Show it fixed' link and parses it back", () => {
    const href = aiPreviewHref({ assessment: "HS-1", photo: 42, products: ["BTH-002", "BTH-009"] });
    expect(href).toBe("/kushalaya/ai-preview?assessment=HS-1&photo=42&products=BTH-002%2CBTH-009");
    const q = new URLSearchParams(href.split("?")[1]);
    expect(parseProductCodes(q.get("products"))).toEqual(["BTH-002", "BTH-009"]);
  });

  it("cleans product codes", () => {
    expect(parseProductCodes(" bth-002, BTH-002,junk, KIT-01 ,")).toEqual(["BTH-002", "KIT-01"]);
    expect(parseProductCodes(null)).toEqual([]);
  });

  it("adds only priced items (integer paise)", () => {
    expect(
      totalWithGst([
        { price_with_gst_paise: 118000, priced: true },
        { price_with_gst_paise: 0, priced: false },
        { price_with_gst_paise: 59000, priced: true },
      ]),
    ).toBe(177000);
  });
});
