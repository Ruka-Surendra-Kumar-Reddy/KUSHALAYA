import { describe, expect, it } from "vitest";
import { planTitle, topPriorities } from "./familyFindings";
import { plainWords } from "./familyWords";
import { familyStatusLine, isStatusVisit, statusWords, withNotedChanges } from "./familyStatus";
import { mergeVisitReports, tidyMissedVisits } from "./familyFeed";
import { forSelf } from "./familySelf";
import { alignSuggestionItems, productFixesFinding } from "../family-catalog";
import { receiptTitle } from "@/components/livewell/family/WalletReceipts";
import { weekTitle } from "@/components/livewell/family/KushLifeWeekCard";

const CHECKS = { safe: "ok", steady: "ok", settled: "ok", connected: "ok" } as const;

describe("one status (round 5)", () => {
  it("Home says 'small changes noted' like Details and the digest", () => {
    const s = familyStatusLine({ elderFirst: "Lakshmi", isSelf: true, checks: { ...CHECKS }, changes: ["Slept poorly"] });
    expect(s.text.startsWith("You are well · small changes noted · ")).toBe(true);
    expect(familyStatusLine({ elderFirst: "Lakshmi", checks: { ...CHECKS } }).text).not.toContain("small changes");
    expect(statusWords("Small changes noted")).toBe("Well · small changes noted");
    expect(statusWords("All good")).toBe("Well");
    expect(statusWords("Watching closely")).toBe("Watching closely");
  });

  it("a visit line never shows all ticks alone when the status noted changes", () => {
    const line = "KushLife check: Safe ✓ · Steady ✓ · Settled ✓ · Connected ✓";
    expect(withNotedChanges(line, ["Slept poorly", "Ate less"])).toBe(`${line} · noted: slept poorly, ate less`);
    expect(withNotedChanges("KushLife: all four checks as usual.", ["Ate less"])).toBe("KushLife: noted ate less.");
    expect(withNotedChanges(line, [])).toBe(line);
    expect(withNotedChanges(`${line} · noted: ate less`, ["Ate less"])).toBe(`${line} · noted: ate less`);
    expect(isStatusVisit("2026-10-07T01:00:00Z", "2026-10-07T01:02:00Z")).toBe(true);
    expect(isStatusVisit("2026-10-06T01:00:00Z", "2026-10-07T01:02:00Z")).toBe(false);
  });
});

describe("Updates feed (round 5)", () => {
  const visit = { id: "v", kind: "visit", title: "Care visit", body: "KushLife check: …", created_at: "2026-10-07T01:00:00Z" };
  const report = { id: "r", kind: "update", title: "Care visit report", body: "KushLife: all four checks as usual.", created_at: "2026-10-07T01:02:00Z" };

  it("one card per visit: the report notice folds into the visit card", () => {
    expect(mergeVisitReports([report, visit]).map((r) => r.id)).toEqual(["v"]);
    // A report with no visit card nearby stays.
    expect(mergeVisitReports([report]).map((r) => r.id)).toEqual(["r"]);
  });

  it("a missed-visit card shown later doesn't promise a call today", () => {
    const missed = {
      id: "m",
      kind: "update",
      title: "Care visit didn’t happen",
      body: "We’re sorry — the care visit planned for Mon 7 Sep, 10:00 AM IST didn’t take place. Your care manager will call you today to find a new time.",
      created_at: "2026-10-07T01:55:00Z",
    };
    const [out] = tidyMissedVisits([missed], new Date("2026-10-12T10:00:00Z"));
    expect(out.body).toContain("will call you to find a new time");
    expect(out.body).not.toContain("today");
    // Posted long after the visit: not "today" even on the same day.
    expect(tidyMissedVisits([missed], new Date("2026-10-07T03:00:00Z"))[0].body).not.toContain("today");
    const fresh = { ...missed, body: missed.body.replace("Mon 7 Sep", "Wed 7 Oct") };
    expect(tidyMissedVisits([fresh], new Date("2026-10-07T03:00:00Z"))[0].body).toContain("call you today");
  });
});

describe("plain plan words (round 5)", () => {
  it.each([
    ["Unsafe shower entry", "Shower hard to step into"],
    ["Unstable bathing position", "No seat for bathing"],
    ["No accessible main entry", "Steps at the front door"],
    ["Kitchen burn / fire hazard", "Risk of burns or fire in the kitchen"],
    ["Missing smoke or CO detectors", "No smoke or gas alarm on each floor"],
    ["Set heater ≤120°F / 49°C", "Set heater ≤49°C"],
    ["Threshold reduction", "Lower the raised step"],
    ["Transfer pole", "Floor-to-ceiling grab pole"],
    ["Pharmacist review for sedating meds", "Ask a pharmacist to check medicines that cause drowsiness"],
  ])("%s -> %s", (raw, plain) => {
    expect(plainWords(raw)).toBe(plain);
  });

  it("plan titles from rubric labels read as problems", () => {
    expect(planTitle("Pathway level and clear")).toBe("Uneven or cluttered pathway");
    expect(planTitle("Loose rugs secured or removed")).toBe("Loose rugs");
    expect(planTitle("Unsafe shower entry")).toBe("Unsafe shower entry");
    expect(topPriorities("Top priorities: Toilet grab bar installed; Unsafe shower entry.")).toEqual([
      "No toilet grab bar",
      "Unsafe shower entry",
    ]);
  });
});

describe("finding ↔ product map (round 5)", () => {
  it("an outdoor light never fixes a dark bedroom", () => {
    expect(productFixesFinding("Outdoor Motion Light", "Bedroom night lighting")).toBe(false);
    expect(productFixesFinding("Outdoor Motion Light", "Adequate entry lighting")).toBe(true);
    expect(productFixesFinding("Motion Night Light", "Bedroom night lighting")).toBe(true);
  });

  it("an urgent finding with no suggested product gets the smoke detector", () => {
    const catalog = [
      { id: 1, name: "Motion Night Light", kind: "product", price_with_gst_paise: 295000 },
      { id: 2, name: "Smoke Detector", kind: "product", price_with_gst_paise: 236000 },
      { id: 3, name: "Outdoor Motion Light", kind: "product", price_with_gst_paise: 295000 },
    ];
    const sug = [
      { product_id: 1, name: "Motion Night Light", priority: "medium" as const, price_with_gst_paise: 295000, reasons: ["Bedroom night lighting"] },
    ];
    const out = alignSuggestionItems(sug, catalog, ["Smoke and CO detectors on each level"]);
    const smoke = out.find((i) => i.product_id === 2);
    expect(smoke?.reasons).toEqual(["Smoke and CO detectors on each level"]);
    expect(smoke?.priority).toBe("high");
    expect(out.some((i) => i.product_id === 3)).toBe(false);
  });
});

describe("self view and money words (round 5)", () => {
  it("words a relative's notice for the elder reading it", () => {
    expect(forSelf("Lakshmi's alert band hasn't checked in since 17 Sep.", "Lakshmi Reddy")).toBe(
      "Your alert band hasn't checked in since 17 Sep.",
    );
    expect(forSelf("Lets your parent sit while bathing.", "Lakshmi Reddy")).toBe("Lets you sit while bathing.");
    expect(forSelf("Lakshmi's alert band", "Lakshmi Reddy", false)).toBe("Lakshmi's alert band");
    expect(weekTitle("Lakshmi", true)).toBe("This week for you");
    expect(weekTitle("Lakshmi", false)).toBe("This week for Lakshmi");
  });

  it("wallet history titles in plain words", () => {
    expect(receiptTitle("Wallet Top-Up")).toBe("Money added to wallet");
    expect(receiptTitle("Care Visit")).toBe("Care visit");
    expect(receiptTitle("Payment for quote Q-12")).toBe("Payment for quote Q-12");
  });
});
