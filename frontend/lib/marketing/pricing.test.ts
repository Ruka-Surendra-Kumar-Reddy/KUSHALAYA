import { describe, expect, it } from "vitest";

import { formatInr, formatUsdApprox, priceForPeriod, USD_INR_RATE } from "./pricing";

describe("priceForPeriod", () => {
  it("reads yearly and monthly prices straight from the catalog", () => {
    expect(priceForPeriod("assurance", "annual")).toBe(55000);
    expect(priceForPeriod("total-care", "annual")).toBe(95000);
    expect(priceForPeriod("assurance", "monthly")).toBe(6000);
    expect(priceForPeriod("total-care", "monthly")).toBe(9900);
    expect(priceForPeriod("privilege", "monthly")).toBe(13500);
    expect(priceForPeriod("signature", "annual")).toBe(160000);
    expect(priceForPeriod("signature", "monthly")).toBe(17500);
  });

  it("returns null for an unknown plan", () => {
    expect(priceForPeriod("nope", "annual")).toBeNull();
  });

  it("never makes monthly cheaper than yearly over a year", () => {
    for (const id of ["assurance", "total-care", "privilege", "signature"]) {
      expect((priceForPeriod(id, "monthly") as number) * 12).toBeGreaterThanOrEqual(priceForPeriod(id, "annual") as number);
    }
  });
});

describe("formatInr", () => {
  it("uses Indian digit grouping", () => {
    expect(formatInr(1200)).toBe("₹1,200");
    expect(formatInr(125000)).toBe("₹1,25,000");
  });
});

describe("USD view", () => {
  it("shows an approximate whole-dollar amount", () => {
    expect(formatUsdApprox(USD_INR_RATE * 136)).toBe("≈ $136");
  });
});
