import { describe, expect, it } from "vitest";

import { CARE_PLAN_CATALOG, EVERY_PLAN_INCLUDES as CARE_PLAN_CATALOG_EVERY } from "@/lib/care-plan-catalog";
import { CARE_PLANS, EVERY_PLAN, MONTHLY_NOTE, PAY_AS_YOU_GO, PLAN_COMPARISON, PLAN_PRICE_LINE, monthlyLine, planById } from "./plans";

describe("care plans", () => {
  it("are built from the catalog: ids, prices and visits", () => {
    expect(CARE_PLANS.map((p) => p.id)).toEqual(["assurance", "total-care", "privilege", "signature"]);
    expect(CARE_PLANS.map((p) => p.annualInr)).toEqual([55000, 95000, 125000, 160000]);
    expect(CARE_PLANS.map((p) => p.monthlyInr)).toEqual([6000, 9900, 13500, 17500]);
    expect(CARE_PLANS.map((p) => p.visitsPerYear)).toEqual(CARE_PLAN_CATALOG.map((p) => p.visitsPerYear));
    for (const p of CARE_PLANS) expect(p.includes).toEqual(CARE_PLAN_CATALOG.find((c) => c.id === p.id)!.inclusions);
  });

  it("never costs more for fewer visits", () => {
    for (let i = 1; i < CARE_PLANS.length; i += 1) {
      expect(CARE_PLANS[i].annualInr).toBeGreaterThan(CARE_PLANS[i - 1].annualInr);
      expect(CARE_PLANS[i].visitsPerYear).toBeGreaterThan(CARE_PLANS[i - 1].visitsPerYear);
    }
  });

  it("marks Privilege, and only Privilege, as most popular", () => {
    expect(CARE_PLANS.filter((p) => p.highlight).map((p) => p.id)).toEqual(["privilege"]);
  });

  it("says 'if paid monthly', never 'effective'", () => {
    expect(monthlyLine(planById("total-care")!)).toBe("₹9,900 a month if paid monthly");
    expect(monthlyLine(planById("assurance")!)).toBe("₹6,000 a month if paid monthly");
    expect(MONTHLY_NOTE).toBe("Prefer flexibility? Monthly billing available on every plan.");
    for (const p of CARE_PLANS) expect(monthlyLine(p)).not.toMatch(/effective/i);
  });

  it("states the starting price and single visit from the catalog", () => {
    expect(PLAN_PRICE_LINE).toContain("₹55,000 a year");
    const single = "Single priority visit — ₹3,400 + ₹100 registration (4 hours, no subscription)";
    expect(PLAN_PRICE_LINE).toContain(single);
    expect(PAY_AS_YOU_GO.items).toContain(single);
    expect(EVERY_PLAN).toEqual(CARE_PLAN_CATALOG_EVERY);
  });

  it("looks a plan up by id", () => {
    expect(planById("privilege")?.shortName).toBe("Privilege");
    expect(planById("care-plus")).toBeUndefined();
  });
});

describe("plan comparison table", () => {
  it("renders a value for every plan in every row", () => {
    for (const row of PLAN_COMPARISON) {
      for (const p of CARE_PLANS) expect(row.value(p).trim()).not.toBe("");
    }
  });

  it("leads with visits and gives the SOS watch only from Privilege up", () => {
    expect(PLAN_COMPARISON[0].label).toBe("Care-manager visits");
    const sos = PLAN_COMPARISON.find((r) => r.label.startsWith("SOS watch"))!;
    expect(CARE_PLANS.map((p) => sos.value(p))).toEqual(["—", "—", "Included", "Included"]);
  });
});
