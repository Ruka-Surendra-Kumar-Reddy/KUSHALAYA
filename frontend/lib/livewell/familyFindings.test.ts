import { describe, expect, it } from "vitest";
import {
  findingNeed,
  findingProblem,
  focusAreas,
  plainAreaName,
  rewordFindingLines,
  summaryWithoutAreas,
  urgentFindings,
} from "./familyFindings";

describe("urgentFindings", () => {
  it("is the one urgent list: critical findings in problem words, no duplicates", () => {
    expect(
      urgentFindings([
        { id: "a", label: "Toilet grab bar installed" },
        { id: "b", label: "Anti-slip flooring" },
        { id: "c", label: "Pathway level and clear" },
        { id: "d", label: "Loose rugs secured or removed" },
        { id: "e", label: "Smoke and CO detectors on each level" },
        { id: "f", label: "Slip-resistant floor" },
      ]),
    ).toEqual([
      "No toilet grab bar",
      "Slippery floors",
      "Uneven or cluttered pathway",
      "Loose rugs",
      "No smoke or gas alarm on each floor",
    ]);
    expect(urgentFindings(null)).toEqual([]);
  });
});

describe("findingProblem", () => {
  it("turns a safe-state label into the problem, one style (no \"— fit one\")", () => {
    expect(findingProblem("Toilet grab bar installed")).toBe("No toilet grab bar");
    expect(findingProblem("Night lights fitted")).toBe("No night lights");
    expect(findingProblem("Smoke alarm in place")).toBe("No smoke alarm");
    expect(findingProblem("Bed transfer support")).toBe("Hard to get in and out of bed");
  });
  it("marks other labels as needing a fix", () => {
    expect(findingProblem("Pathway level and clear")).toBe("Uneven or cluttered pathway");
    expect(findingProblem("Grab bar")).toBe("Grab bar — needs fixing");
  });
});

describe("findingNeed", () => {
  it("gives just the problem", () => {
    expect(findingNeed("Toilet grab bar installed")).toBe("No toilet grab bar");
    expect(findingNeed("SOS button available")).toBe("No SOS button");
    expect(findingNeed("Pathway level and clear")).toBe("Uneven or cluttered pathway");
  });
});

describe("focus areas", () => {
  const s =
    "Safety Score 40/100 (High risk). Top priorities: Grab bar. Areas to focus on: 1. Home Safety 0, 7. Emergency Preparedness 40, 3. Health & Wellness 41, 2. Mobility 60.";
  it("parses the lowest three from the summary, without section numbers", () => {
    expect(focusAreas(s)).toEqual([
      { name: "Home safety", score: 0 },
      { name: "Emergency preparedness", score: 40 },
      { name: "Health & wellness", score: 41 },
    ]);
  });
  it("prefers domain scores", () => {
    expect(
      focusAreas(s, [
        { title: "2. Mobility", score: 10 },
        { title: "Home Safety", score: 50 },
      ]),
    ).toEqual([
      { name: "Mobility", score: 10 },
      { name: "Home safety", score: 50 },
    ]);
  });
  it("drops the areas sentence from the text", () => {
    expect(summaryWithoutAreas(s)).toBe("Safety Score 40/100 (High risk). Top priorities: Grab bar.");
    expect(plainAreaName("4) ADL Support")).toBe("ADL support");
  });
});

describe("rewordFindingLines", () => {
  it("rewords the listed findings only", () => {
    const body =
      "The home safety assessment found things that need fixing first:\n- Toilet grab bar installed\n- Pathway level and clear\n- and 2 more\nYour care team will call you.";
    expect(rewordFindingLines(body)).toBe(
      "The home safety assessment found things that need fixing first:\n- No toilet grab bar\n- Uneven or cluttered pathway\n- and 2 more\nYour care team will call you.",
    );
    expect(rewordFindingLines("- No toilet grab bar — fit one")).toBe("- No toilet grab bar");
  });
});
