import { describe, expect, it } from "vitest";
import { FINDING_WORDS, findingNeed, findingProblem, rewordFindingLines, topPriorities } from "./familyFindings";
import { plainWords } from "./familyWords";
import { fixesTotal, groupByNeed } from "./familyPlan";
import { alignRecommendations, alignSuggestionItems, productFixesFinding } from "../family-catalog";
import { collapseVisitChains, splitFeedBody, teamReplies } from "./familyFeed";
import { isBackdatedSchedule } from "./familyTime";
import { canAskRating, isCompletedCareVisit } from "./familyVisit";
import { contactsToCall, familyStatusLine } from "./familyStatus";

describe("finding wording map", () => {
  it.each([
    ["Anti-slip flooring", "Slippery floors"],
    ["Pathway level and clear", "Uneven or cluttered pathway"],
    ["Loose rugs secured or removed", "Loose rugs"],
    ["Emergency contacts posted", "No emergency contacts posted"],
    ["Bedroom night lighting", "No bedroom night light"],
    ["Toilet height appropriate", "Toilet too low or too high"],
  ])("%s -> %s", (label, words) => {
    expect(findingNeed(label)).toBe(words);
    expect(findingProblem(label)).toBe(words);
  });
  it("still words safe-state labels as the problem", () => {
    expect(findingNeed("Shower chair available")).toBe("No shower chair");
    expect(findingNeed("Shower grab bar installed")).toBe("No shower grab bar");
  });
  it("never words a mapped label as done or with a bare '— needs fixing'", () => {
    for (const words of Object.values(FINDING_WORDS)) {
      expect(words).not.toMatch(/installed|needs fixing/i);
    }
  });
  it("does not reword an already-worded line", () => {
    expect(rewordFindingLines("- Loose rugs")).toBe("- Loose rugs");
  });
});

describe("top priorities", () => {
  it("lists up to three priorities instead of a clamped sentence", () => {
    const s = "Safety Score 43/100 (High risk). Top priorities: Unsafe shower entry; Anti-slip flooring; Grab bar; Loose rugs. Areas to focus on: Home Safety 0.";
    expect(topPriorities(s)).toEqual(["Unsafe shower entry", "Slippery floors", "Grab bar"]);
    expect(topPriorities("No priorities here")).toEqual([]);
  });
});

describe("plain words", () => {
  it("drops doubled glosses on area names", () => {
    expect(plainWords("Activities of Daily Living (ADLs)")).toBe("Daily self-care");
    expect(plainWords("Household tasks (IADLs)")).toBe("Household tasks");
    expect(plainWords("Household tasks (household tasks)")).toBe("Household tasks");
  });
  it("uses Celsius and plain walking words", () => {
    expect(plainWords("Set the geyser to ≤120°F")).toBe("Set the geyser to ≤49°C");
    expect(plainWords("Unsteady gait")).toBe("Unsteady walking");
    expect(plainWords("Gait assessment")).toBe("Walking check");
  });
});

describe("one fixes total", () => {
  it("adds the cheapest priced option per need and counts unpriced needs", () => {
    const needs = groupByNeed([
      { product_id: 1, name: "Grab bar A", reasons: ["Toilet grab bar installed"], price_with_gst_paise: 300000 },
      { product_id: 2, name: "Grab bar B", reasons: ["Toilet grab bar installed"], price_with_gst_paise: 200000 },
      { product_id: 3, name: "Rug grips", reasons: ["Loose rugs secured or removed"], price_with_gst_paise: null },
    ]);
    expect([...needs.keys()]).toEqual(["No toilet grab bar", "Loose rugs"]);
    expect(fixesTotal(needs)).toEqual({ paise: 200000, priced: 1, unpriced: 1 });
  });
});

describe("product ↔ finding map", () => {
  it("rejects pairs the keyword match got wrong", () => {
    expect(productFixesFinding("Adult bed rail", "Bedroom night lighting")).toBe(false);
    expect(productFixesFinding("Bathroom emergency pull cord", "Emergency contacts posted")).toBe(false);
    expect(productFixesFinding("L-Shaped Grab Bar", "Toilet grab bar installed")).toBe(false);
    expect(productFixesFinding("L-Shaped Grab Bar", "Shower grab bar installed")).toBe(true);
    expect(productFixesFinding("Motion Night Light", "Bedroom night lighting")).toBe(true);
  });
  it("moves findings to the products that fix them", () => {
    const map = alignRecommendations(
      [
        { id: 1, name: "Adult bed rail", reasons: ["Bedroom night lighting", "Bed transfer support"] },
        { id: 2, name: "Bathroom emergency pull cord", reasons: ["Emergency contacts posted"] },
        { id: 3, name: "L-Shaped Grab Bar", reasons: ["Toilet grab bar installed", "Shower grab bar installed"] },
      ],
      [
        { id: 10, name: "Motion Night Light" },
        { id: 11, name: "Emergency contact card" },
        { id: 12, name: "Toilet safety rail" },
      ],
    );
    expect(map.get(1)).toEqual(["Bed transfer support"]);
    expect(map.has(2)).toBe(false);
    expect(map.get(3)).toEqual(["Shower grab bar installed"]);
    expect(map.get(10)).toEqual(["Bedroom night lighting"]);
    expect(map.get(11)).toEqual(["Emergency contacts posted"]);
    expect(map.get(12)).toEqual(["Toilet grab bar installed"]);
  });
  it("builds suggestion items for added catalog products", () => {
    const out = alignSuggestionItems(
      [{ product_id: 1, name: "Adult bed rail", priority: "high", price_with_gst_paise: 100, reasons: ["Bedroom night lighting"] }],
      [{ id: 10, name: "Motion Night Light", kind: "product", price_with_gst_paise: 295000 }],
    );
    expect(out).toEqual([
      { product_id: 10, name: "Motion Night Light", priority: "medium", price_with_gst_paise: 295000, reasons: ["Bedroom night lighting"] },
    ]);
  });
});

describe("updates feed", () => {
  it("drops a schedule notice whose body date was already past", () => {
    expect(isBackdatedSchedule("Care visit scheduled", "2026-10-07T05:00:00Z", "Care visit on Mon 7 Sep, 10:00 am.")).toBe(true);
    expect(isBackdatedSchedule("Care visit scheduled", "2026-10-07T05:00:00Z", "Care visit on Sat 17 Oct, 10:00 am.")).toBe(false);
  });
  it("collapses a visit's notices into its latest state and drops an early 'on the way'", () => {
    const rows = [
      { id: "4", kind: "update", title: "Care visit cancelled", body: "Care visit on Sat 17 Oct, 10:00 am was cancelled.", created_at: "2026-10-09T05:00:00Z" },
      { id: "3", kind: "update", title: "Care visit updated", body: "Care visit is now on Sat 17 Oct, 10:00 am with Anita.", created_at: "2026-10-08T05:00:00Z" },
      { id: "2", kind: "update", title: "Anita is on the way", body: "Anita is on the way for the care visit.", created_at: "2026-10-07T06:00:00Z" },
      { id: "1", kind: "update", title: "Care visit scheduled", body: "Care visit on Sat 17 Oct, 10:00 am with Anita.", created_at: "2026-10-07T05:00:00Z" },
      { id: "0", kind: "update", title: "Care visit scheduled", body: "Care visit on Mon 7 Sep, 10:00 am.", created_at: "2026-10-07T04:00:00Z" },
      { id: "m", kind: "message", title: "Message", body: "Hello", created_at: "2026-10-06T04:00:00Z" },
    ];
    expect(collapseVisitChains(rows).map((r) => r.id)).toEqual(["4", "m"]);
  });
  it("keeps an 'on the way' on the visit day until the arrival replaces it", () => {
    const rows = [
      { id: "b", kind: "update", title: "Anita has arrived", body: "Anita checked in for the care visit.", created_at: "2026-10-17T04:40:00Z" },
      { id: "a", kind: "update", title: "Anita is on the way", body: "Anita is on the way for the care visit.", created_at: "2026-10-17T04:10:00Z" },
    ];
    expect(collapseVisitChains(rows).map((r) => r.id)).toEqual(["b"]);
    expect(collapseVisitChains(rows.slice(1)).map((r) => r.id)).toEqual(["a"]);
  });
  it("puts the follow-up sentence after the list", () => {
    const out = splitFeedBody("Found:\n- Loose rugs\n- Slippery floors — needs fixing Your care team will call you.");
    expect(out.items).toEqual(["Loose rugs", "Slippery floors — needs fixing"]);
    expect(out.outro).toBe("Your care team will call you.");
    expect(splitFeedBody("Found:\n- a\n- b\nWe will call.").outro).toBe("We will call.");
  });
  it("help panel shows only team replies to the family, newest first", () => {
    const m = (id: string, role: string, at: string) => ({ id, body: id, sender_role: role, sender_name: "Ravi", created_at: at });
    const rows = [m("greet", "team", "2026-10-01"), m("q", "family", "2026-10-02"), m("r1", "team", "2026-10-03"), m("r2", "team", "2026-10-04")];
    expect(teamReplies(rows).map((r) => r.id)).toEqual(["r2", "r1"]);
  });
});

describe("visit report rules", () => {
  const now = Date.parse("2026-10-12T00:00:00Z");
  it("asks for a rating only on recent completed care visits", () => {
    expect(canAskRating({ id: "job-5", visit_type: "Care visit", status: "completed", visited_at: "2026-10-07T00:00:00Z" }, now)).toBe(true);
    expect(canAskRating({ id: "job-5", visit_type: "Care visit", status: "completed", visited_at: "2026-09-01T00:00:00Z" }, now)).toBe(false);
    expect(canAskRating({ id: "v-1", visit_type: "Baseline profile visit", status: "completed", visited_at: "2026-10-07T00:00:00Z" }, now)).toBe(false);
  });
  it("never treats an assessment or baseline as a care visit (no NPS)", () => {
    expect(isCompletedCareVisit({ id: "job-9", visit_type: "Home safety assessment", status: "completed" })).toBe(false);
    expect(isCompletedCareVisit({ id: "job-4", visit_type: "Care visit", status: "completed" })).toBe(true);
  });
});

describe("one status", () => {
  it("never shows checks OK on their own when the carer noted changes", () => {
    const s = familyStatusLine({
      elderFirst: "Lakshmi",
      lastVisitAt: null,
      checks: { safe: "ok", steady: "ok", settled: "ok", connected: "ok" },
      changes: ["Ate less", "Slept poorly"],
    });
    expect(s.text).toContain("4/4 checks OK · ate less, slept poorly");
  });
  it("leaves the senior out of their own emergency contacts", () => {
    const rows = [
      { name: "Lakshmi Reddy", relationship: "Senior (at home)" },
      { name: "Arjun Reddy", relationship: "Son" },
    ];
    expect(contactsToCall(rows, "Lakshmi Reddy").map((c) => c.name)).toEqual(["Arjun Reddy"]);
  });
});
