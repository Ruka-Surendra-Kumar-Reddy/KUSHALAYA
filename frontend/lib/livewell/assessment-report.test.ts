import { describe, expect, it } from "vitest";

import { createEmptyAssessment } from "./assessment";
import {
  buildReportNarrativeBrief,
  formatAssessmentReport,
} from "./assessment-report";
import { DEFAULT_SAFETY_CATEGORIES } from "./rubric-defaults";
import { DEFAULT_SOLUTION_LIBRARY } from "./solution-defaults";
import { SEEDED_CATALOG_PRODUCTS } from "./catalog-product-seed";
import { DEFAULT_SAFEHOME_PRICING } from "./pricing-defaults";

describe("assessment report", () => {
  it("includes care pathway, solution names, and evidence", () => {
    const a = createEmptyAssessment();
    a.clientFirstName = "Lakshmi";
    a.clientLastName = "Reddy";
    a.assessorName = "Anita";
    a.residentProfile.livesAlone = true;
    a.residentProfile.medicalConditions = ["Dementia"];
    a.ratings.home_safety_toilet_grab_bar_installed = "unsafe";

    const text = formatAssessmentReport(
      a,
      DEFAULT_SAFETY_CATEGORIES,
      DEFAULT_SOLUTION_LIBRARY,
      { products: SEEDED_CATALOG_PRODUCTS, packages: [] },
      DEFAULT_SAFEHOME_PRICING,
    );

    expect(text).toContain("CARE PATHWAY");
    expect(text).toContain("Assisted Living at Home");
    expect(text).toContain("LW-HS-BTH-001");
    expect(text).toContain("Improve toilet transfer safety");
    expect(text).toContain("Evidence A");
    expect(text).toContain("not free-form AI");
    expect(text).toContain("AI ROOM VISUALIZATIONS (REPORT MERGE)");
    expect(text).toContain("NOT INCORPORATED");
  });

  it("builds AI narrative brief without inventing SKUs", () => {
    const a = createEmptyAssessment();
    a.ratings.home_safety_toilet_grab_bar_installed = "unsafe";
    const brief = buildReportNarrativeBrief(
      a,
      DEFAULT_SAFETY_CATEGORIES,
      DEFAULT_SOLUTION_LIBRARY,
    );
    expect(brief.constraint).toMatch(/Do not invent/);
    expect(Array.isArray(brief.topRecommendations)).toBe(true);
  });
});
