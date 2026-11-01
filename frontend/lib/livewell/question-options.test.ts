import { describe, expect, it } from "vitest";
import {
  answerLabel,
  cleanOptions,
  joinHelp,
  questionAsk,
  questionOptions,
  splitHelp,
  standardOptions,
} from "./question-options";

const MAPPED = "home_safety_toilet_grab_bar_installed";

describe("question options", () => {
  it("uses the caregiver wording when the question is in the map", () => {
    const opts = standardOptions({ id: MAPPED, label: "Grab bar" });
    expect(opts.map((o) => o.rating)).toEqual(["excellent", "acceptable", "unsafe", "na"]);
    expect(opts[0].label).toBe("Yes, fixed firmly and used");
    expect(questionAsk({ id: MAPPED, label: "Grab bar" })).toBe("Is there a grab bar by the toilet?");
  });

  it("falls back to help text lines, then generic", () => {
    const help = "Look for: a bar\n★ Excellent: Firm bar\n~ Acceptable: Loose\n✕ Unsafe: None\n— N/A: Never alone\nTip: x";
    expect(standardOptions({ id: "x", help })).toEqual([
      { label: "Firm bar", rating: "excellent" },
      { label: "Loose", rating: "acceptable" },
      { label: "None", rating: "unsafe" },
      { label: "Never alone", rating: "na" },
    ]);
    expect(standardOptions({ id: "x" }).map((o) => o.label)).toEqual(["Safe", "Needs attention", "Risk", "Doesn't apply"]);
    expect(questionAsk({ id: "x", label: "Lighting" })).toBe("Lighting");
  });

  it("long help lines become the plain word for their rating", () => {
    const help = `★ Excellent: Firm bar\n~ Acceptable: ${"x".repeat(61)}\n✕ Unsafe: ${"y".repeat(60)}`;
    expect(standardOptions({ id: "x", help })).toEqual([
      { label: "Firm bar", rating: "excellent" },
      { label: "Needs attention", rating: "acceptable" },
      { label: "y".repeat(60), rating: "unsafe" },
    ]);
  });

  it("custom options and ask win; cleaning drops bad ones and caps at 8", () => {
    const item = { id: MAPPED, ask: " Bar? ", options: [{ label: " Yes ", rating: "excellent" as const }] };
    expect(questionOptions(item)).toEqual([{ label: "Yes", rating: "excellent" }]);
    expect(questionAsk(item)).toBe("Bar?");
    expect(cleanOptions([{ label: "", rating: "na" }, { label: "a", rating: "bad" }, null])).toEqual([]);
    expect(cleanOptions(Array(12).fill({ label: "a", rating: "unsafe" }))).toHaveLength(8);
    // Cleared options mean standard ones again.
    expect(questionOptions({ id: MAPPED, options: [] })[0].label).toBe("Yes, fixed firmly and used");
  });

  it("answer label prefers the tapped option", () => {
    const item = { id: "x", options: [{ label: "A", rating: "unsafe" as const }, { label: "B", rating: "unsafe" as const }] };
    expect(answerLabel(item, "unsafe")).toBe("A");
    expect(answerLabel(item, "unsafe", "B")).toBe("B");
    expect(answerLabel(item, null)).toBeUndefined();
  });

  it("splits and rejoins help without losing text", () => {
    const help = "Look for: a firm bar\n★ Excellent: Firm\nTip: test it";
    const { lookFor, rest } = splitHelp(help);
    expect(lookFor).toBe("a firm bar");
    expect(rest).toBe("★ Excellent: Firm\nTip: test it");
    expect(joinHelp(lookFor, rest)).toBe(help);
    expect(splitHelp("Check the bar")).toEqual({ lookFor: "Check the bar", rest: "" });
  });
});
