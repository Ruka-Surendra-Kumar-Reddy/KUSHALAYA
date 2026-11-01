import { describe, expect, it } from "vitest";

import { LWA_CATEGORIES } from "./lwa-rubric";
import {
  countSkippedItems,
  getApplicableCategories,
  getApplicableItems,
} from "./conditional";
import { evaluateConditionalRule } from "./conditional-rules";
import { EMPTY_RESIDENT_PROFILE, type ResidentProfile } from "./resident-profile";

const fullProfile: ResidentProfile = {
  ...EMPTY_RESIDENT_PROFILE,
  hasStairs: true,
  livesAlone: true,
  mobilityDevice: "wheelchair",
  hasBalcony: true,
  smartHomeAssessment: true,
  smartHomeAdvanced: true,
  domesticHelper: true,
};

const minimalProfile: ResidentProfile = {
  ...EMPTY_RESIDENT_PROFILE,
  hasStairs: false,
  livesAlone: false,
  mobilityDevice: "none",
  hasBalcony: false,
  smartHomeAssessment: false,
  smartHomeAdvanced: false,
  domesticHelper: false,
  livesWithSpouse: true,
};

describe("conditional rules (KAA)", () => {
  it("skips stairs items when no stairs", () => {
    expect(evaluateConditionalRule("unless_has_stairs", minimalProfile)).toBe(true);
    expect(evaluateConditionalRule("unless_has_stairs", fullProfile)).toBe(false);
  });

  it("skips wheelchair items when not wheelchair user", () => {
    expect(evaluateConditionalRule("unless_wheelchair_user", minimalProfile)).toBe(true);
    expect(evaluateConditionalRule("unless_wheelchair_user", fullProfile)).toBe(false);
  });

  it("skips entrance railing and stairs items on stair-free profile", () => {
    const items = getApplicableItems(LWA_CATEGORIES, minimalProfile);
    const labels = items.map((i) => i.label);
    expect(labels).not.toContain("Entrance railing if needed");
    expect(labels).not.toContain("Stairs manageable or alternative exists");
  });

  it("keeps stairs-related mobility items when stairs present", () => {
    const items = getApplicableItems(LWA_CATEGORIES, fullProfile);
    const labels = items.map((i) => i.label);
    expect(labels).toContain("Stairs manageable or alternative exists");
    expect(labels).toContain("Door widths / thresholds accessible");
  });

  it("always exposes the twelve KAA domains", () => {
    const cats = getApplicableCategories(LWA_CATEGORIES, minimalProfile);
    expect(cats.map((c) => c.id)).toEqual([
      "home_safety",
      "mobility",
      "health_wellness",
      "adl",
      "iadl",
      "cognitive_emotional",
      "emergency",
      "home_condition",
      "technology",
      "family_support",
      "financial_benefits",
      "lifestyle",
    ]);
  });

  it("skips some items for typical apartment without stairs", () => {
    const apartment: ResidentProfile = {
      ...minimalProfile,
      dwellingType: "apartment",
      hasBalcony: false,
    };
    const allItems = LWA_CATEGORIES.flatMap((c) => c.items).length;
    const applicable = getApplicableItems(LWA_CATEGORIES, apartment).length;
    const skipped = countSkippedItems(LWA_CATEGORIES, apartment);
    expect(skipped).toBeGreaterThan(0);
    expect(applicable).toBeLessThan(allItems);
    expect(applicable).toBeGreaterThan(40);
  });
});
