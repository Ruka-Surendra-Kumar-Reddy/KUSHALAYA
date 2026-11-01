import { describe, expect, it } from "vitest";

import { DEFAULT_SAFETY_CATEGORIES } from "./rubric-defaults";
import { LWA_RAW_MAX } from "./lwa-rubric";
import {
  categoryScore,
  itemPoints,
  normalizedScore,
  safetyAge,
  safetyGradeFromScore,
  type ItemRating,
} from "./assessment";
import { EMPTY_RESIDENT_PROFILE } from "./resident-profile";

describe("LiveWell360 Independence Score", () => {
  const categories = DEFAULT_SAFETY_CATEGORIES;

  it("uses KAA Independence Score™ bands on 0–100 score", () => {
    expect(safetyGradeFromScore(96).grade).toBe("Excellent");
    expect(safetyGradeFromScore(80).grade).toBe("Good");
    expect(safetyGradeFromScore(70).grade).toBe("Moderate Risk");
    expect(safetyGradeFromScore(50).grade).toBe("High Risk");
    expect(safetyGradeFromScore(30).grade).toBe("Critical");
  });

  it("scores excellent/acceptable/unsafe with legacy pass/partial/fail aliases", () => {
    expect(itemPoints("excellent", 5)).toBe(5);
    expect(itemPoints("acceptable", 5)).toBe(2.5);
    expect(itemPoints("unsafe", 5)).toBe(0);
    expect(itemPoints("pass", 5)).toBe(5);
    expect(itemPoints("partial", 5)).toBe(2.5);
    expect(itemPoints("fail", 5)).toBe(0);
    expect(itemPoints("na", 5)).toBe(0);
  });

  it("normalizes all-excellent answers to 100", () => {
    const ratings: Record<string, ItemRating> = {};
    for (const cat of categories) {
      for (const item of cat.items) {
        ratings[item.id] = "excellent";
      }
    }
    expect(normalizedScore(categories, ratings, EMPTY_RESIDENT_PROFILE)).toBe(100);
    expect(LWA_RAW_MAX).toBe(100);
    expect(categoryScore(categories[0], ratings, EMPTY_RESIDENT_PROFILE)).toBeGreaterThan(0);
  });

  it("derives risk level and safety age", () => {
    // One vocabulary since Sept 2026: the Independence band is the risk label
    // (riskLevel() with its own thresholds was removed).
    const statuses = [90, 80, 70, 50, 10].map((n) => safetyGradeFromScore(n).status);
    expect(new Set(statuses).size).toBe(5);
    expect(safetyAge(74, 65)).toBe(89);
  });
});
