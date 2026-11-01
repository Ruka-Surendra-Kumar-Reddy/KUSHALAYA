import { describe, expect, it } from "vitest";

import { VISIT_PLAN_ID, cleanCouponCode, cycleForPeriod, earliestVisitDate, shownPrice, type PlanQuote } from "./plan-checkout";

describe("plan checkout helpers", () => {
  it("maps the card period to the API cycle", () => {
    expect(cycleForPeriod("annual")).toBe("yearly");
    expect(cycleForPeriod("monthly")).toBe("monthly");
  });

  it("cleans coupon codes", () => {
    expect(cleanCouponCode(" paynow3 ")).toBe("PAYNOW3");
    expect(cleanCouponCode("pay now5!")).toBe("PAYNOW5");
  });

  it("falls back to the catalog price without a matching quote", () => {
    expect(shownPrice("privilege", "yearly", null)).toEqual({
      listPaise: 12_500_000, discountPaise: 0, amountPaise: 12_500_000, coupon: null,
    });
    expect(shownPrice("assurance", "monthly", null)?.amountPaise).toBe(600_000);
    expect(shownPrice("gold", "yearly", null)).toBeNull();
  });

  it("uses the server quote only for the same plan and cycle", () => {
    const quote: PlanQuote = {
      plan_id: "privilege", plan_name: "KushAlaya Privilege", billing_cycle: "yearly",
      list_paise: 12_500_000, discount_paise: 375_000, amount_paise: 12_125_000, coupon_code: "PAYNOW3",
    };
    expect(shownPrice("privilege", "yearly", quote)).toEqual({
      listPaise: 12_500_000, discountPaise: 375_000, amountPaise: 12_125_000, coupon: "PAYNOW3",
    });
    expect(shownPrice("privilege", "monthly", quote)?.discountPaise).toBe(0);
  });

  it("prices the single visit as visit + registration, bought once", () => {
    expect(shownPrice(VISIT_PLAN_ID, "once", null)).toEqual({ listPaise: 350_000, discountPaise: 0, amountPaise: 350_000, coupon: null });
    expect(shownPrice(VISIT_PLAN_ID, "yearly", null)).toBeNull();
    expect(shownPrice("privilege", "once", null)).toBeNull();
  });

  it("books a visit from tomorrow", () => {
    expect(earliestVisitDate(new Date(2026, 9, 31, 23, 30))).toBe("2026-11-01");
    expect(earliestVisitDate(new Date(2026, 11, 31, 8))).toBe("2027-01-01");
  });
});
