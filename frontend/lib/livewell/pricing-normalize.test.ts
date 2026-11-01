import { describe, expect, it } from "vitest";

import { normalizePricingConfig } from "./pricing";

describe("normalizePricingConfig", () => {
  it("clamps percents and rejects unknown enums", () => {
    const out = normalizePricingConfig({
      margin_type: "bonus" as never,
      round_off_rule: "nearest_1" as never,
      default_margin_percent: 250,
      gst_percent: 18,
      use_vendor_cost_for_margin: true,
    });
    expect(out.margin_type).toBe("percent");
    expect(["none", "nearest_50", "nearest_100"]).toContain(out.round_off_rule);
    expect(out.default_margin_percent).toBeLessThanOrEqual(100);
    expect(out.use_vendor_cost_for_margin).toBe(true);
  });

  it("keeps valid fixed margin", () => {
    const out = normalizePricingConfig({
      margin_type: "fixed",
      round_off_rule: "none",
      fixed_margin_inr: 400,
      gst_percent: 5,
    });
    expect(out.margin_type).toBe("fixed");
    expect(out.round_off_rule).toBe("none");
    expect(out.fixed_margin_inr).toBe(400);
    expect(out.gst_percent).toBe(5);
  });
});
