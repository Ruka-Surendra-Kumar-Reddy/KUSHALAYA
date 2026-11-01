import { describe, expect, it } from "vitest";

import { withoutMarketingPrices } from "./without-prices";

describe("withoutMarketingPrices", () => {
  it("returns empty input unchanged", () => {
    expect(withoutMarketingPrices("")).toBe("");
  });

  it("strips rupee amounts and hyderabad rate lines", () => {
    const text =
      "Grab bar ₹1,200–₹1,800 /unit. Hyderabad: from ₹2,500. Safe install.";
    const out = withoutMarketingPrices(text);
    expect(out).not.toMatch(/₹/);
    expect(out.toLowerCase()).not.toContain("hyderabad:");
    expect(out).toContain("Grab bar");
  });

  it("collapses leftover separators", () => {
    expect(withoutMarketingPrices("Hello   ·  ·  world")).toBe("Hello world");
  });
});
