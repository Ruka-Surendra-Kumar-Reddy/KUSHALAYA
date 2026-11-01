import { describe, expect, it } from "vitest";
import {
  defaultRating,
  previewProductCodes,
  roomChipText,
  rupeesInclGst,
  showItFixedHref,
  splitByBand,
  type HazardProduct,
  type RoomHazard,
} from "./aiHazardCheck";

const prod = (code: string, gst: number | null = 118000): HazardProduct => ({
  product_code: code,
  name: code,
  category: "",
  price_paise: 100000,
  price_with_gst_paise: gst,
  price_label: "Quote",
});

describe("aiHazardCheck helpers", () => {
  it("builds the Show it fixed link the preview page expects", () => {
    expect(showItFixedHref({ assessmentId: "ASM-1", documentId: 42, productCodes: ["BTH-001", "BTH-006", "BTH-001"] })).toBe(
      "/kushalaya/ai-preview?assessment=ASM-1&photo=42&products=BTH-001,BTH-006",
    );
    expect(showItFixedHref({ documentId: 7, productCodes: [] })).toBe("/kushalaya/ai-preview?photo=7");
  });

  it("prefers physical products over services for the preview", () => {
    expect(previewProductCodes([prod("SVC-002"), prod("BTH-001"), prod("BTH-004")])).toEqual(["BTH-001", "BTH-004"]);
    expect(previewProductCodes([prod("SVC-002")])).toEqual(["SVC-002"]);
  });

  it("formats room chips and prices", () => {
    expect(roomChipText({ room: "bathroom", label: "Bathroom", hazards: 3, urgent: 2 })).toBe("Bathroom: 3 hazards · 2 urgent");
    expect(roomChipText({ room: "entry", label: "Entrance", hazards: 1, urgent: 0 })).toBe("Entrance: 1 hazard");
    expect(rupeesInclGst(prod("X"))).toBe("₹1,180 incl. GST");
    expect(rupeesInclGst(prod("X", null))).toBe("Quote");
  });

  it("hides low confidence and picks the default rating", () => {
    const h = (band: RoomHazard["band"]) => ({ band }) as RoomHazard;
    const { shown, low } = splitByBand([h("high"), h("check"), h("low")]);
    expect(shown).toHaveLength(2);
    expect(low).toHaveLength(1);
    expect(defaultRating({ severity: "watch" })).toBe("acceptable");
    expect(defaultRating({ severity: "urgent" })).toBe("unsafe");
  });
});
