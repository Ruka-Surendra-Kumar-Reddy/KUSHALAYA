import { describe, expect, it } from "vitest";

import { createEmptyAssessment } from "./assessment";
import { DEFAULT_SAFETY_CATALOG } from "./catalog-defaults";
import { DEFAULT_SAFEHOME_PRICING } from "./pricing-defaults";
import { buildQuoteReportText, hasQuoteableFindings } from "./quote-report";
import { DEFAULT_SAFETY_CATEGORIES } from "./rubric-defaults";
import { DEFAULT_SOLUTION_LIBRARY } from "./solution-defaults";

describe("quote report", () => {
  it("detects quoteable findings from partial ratings", () => {
    const assessment = createEmptyAssessment();
    expect(hasQuoteableFindings(assessment, DEFAULT_SAFETY_CATEGORIES, DEFAULT_SOLUTION_LIBRARY)).toBe(
      false,
    );
    assessment.ratings.home_safety_toilet_grab_bar_installed = "unsafe";
    expect(hasQuoteableFindings(assessment, DEFAULT_SAFETY_CATEGORIES, DEFAULT_SOLUTION_LIBRARY)).toBe(
      true,
    );
  });

  it("builds quote text without full checklist completion", () => {
    const assessment = createEmptyAssessment();
    assessment.ratings.home_safety_toilet_grab_bar_installed = "unsafe";
    const text = buildQuoteReportText(
      assessment,
      DEFAULT_SAFETY_CATEGORIES,
      DEFAULT_SOLUTION_LIBRARY,
      DEFAULT_SAFETY_CATALOG,
      DEFAULT_SAFEHOME_PRICING,
    );
    expect(text).toContain("partial assessment");
    expect(text).toContain("GRAND TOTAL");
  });
});
