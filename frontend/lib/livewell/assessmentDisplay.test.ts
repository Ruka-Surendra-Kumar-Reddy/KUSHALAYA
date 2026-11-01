import { describe, expect, it } from "vitest";
import {
  assessmentOptionLabel,
  draftScoreText,
  isScoreFinal,
  shortDate,
  stripAssessmentIdSuffix,
} from "./assessmentDisplay";

describe("stripAssessmentIdSuffix", () => {
  it("drops the (hsa-…) suffix from document titles", () => {
    expect(stripAssessmentIdSuffix("Bathroom grab bar (hsa-1784559753603-l3qdo0e)")).toBe("Bathroom grab bar");
    expect(stripAssessmentIdSuffix("Consent Form (HS-12ab)")).toBe("Consent Form");
  });
  it("leaves other names and brackets alone", () => {
    expect(stripAssessmentIdSuffix("Report (final).pdf")).toBe("Report (final).pdf");
    expect(stripAssessmentIdSuffix("")).toBe("");
    expect(stripAssessmentIdSuffix(null)).toBe("");
  });
});

describe("assessmentOptionLabel", () => {
  it("uses the completed date, status word and assessor", () => {
    expect(
      assessmentOptionLabel({
        status: "completed",
        completed_at: "2026-08-06T05:00:00",
        created_at: "2026-08-01T05:00:00",
        assessor: "Ravi Kumar",
      }),
    ).toBe("Home safety assessment · 6 Aug 2026 · Completed · by Ravi Kumar");
  });
  it("falls back to the created date and omits a missing assessor", () => {
    expect(assessmentOptionLabel({ status: "draft", created_at: "2026-08-01T05:00:00Z", assessor: "" })).toBe(
      "Home safety assessment · 1 Aug 2026 · Draft",
    );
  });
  it("never shows the raw id", () => {
    expect(assessmentOptionLabel({ status: "completed" })).toBe("Home safety assessment · Completed");
  });
});

describe("draft score", () => {
  it("only completed assessments have a final score", () => {
    expect(isScoreFinal("completed")).toBe(true);
    expect(isScoreFinal("draft")).toBe(false);
    expect(isScoreFinal(undefined)).toBe(false);
  });
  it("shows the rated percentage", () => {
    expect(draftScoreText(38)).toBe("Draft · 38% rated");
    expect(draftScoreText(19.4)).toBe("Draft · 19% rated");
    expect(draftScoreText(NaN)).toBe("Draft · 0% rated");
  });
  it("formats dates in IST", () => {
    expect(shortDate("2026-08-05T20:00:00")).toBe("6 Aug 2026");
    expect(shortDate("bad")).toBe("");
  });
});

describe("ageFromDob", () => {
  it("counts whole years, before and after the birthday", async () => {
    const { ageFromDob } = await import("./assessmentDisplay");
    expect(ageFromDob("1945-03-15", new Date("2026-10-11T06:00:00Z"))).toBe("81");
    expect(ageFromDob("1945-12-15", new Date("2026-10-11T06:00:00Z"))).toBe("80");
    expect(ageFromDob(null)).toBe("");
    expect(ageFromDob("not a date")).toBe("");
  });
});

describe("assessmentTitle", () => {
  it("uses the name, else a dated draft title", async () => {
    const { assessmentTitle } = await import("./assessmentDisplay");
    expect(assessmentTitle("Lakshmi Rao", "2026-08-06T10:00:00Z")).toBe("Lakshmi Rao");
    expect(assessmentTitle("", "2026-08-06T10:00:00Z")).toMatch(/^Draft · .*2026/);
    expect(assessmentTitle("", null)).toBe("Draft assessment");
  });
});
