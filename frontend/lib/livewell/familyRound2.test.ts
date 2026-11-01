import { describe, expect, it } from "vitest";
import { familyClock, familyDate, familyTime, isBackdatedSchedule, tidyDates } from "./familyTime";
import { photoCaption, plainWords, withoutContextLines } from "./familyWords";
import { familyStatusLine, requestStep } from "./familyStatus";
import { parseRupeeRange, projectedScore, totalCostRange } from "./familyPlan";

const NOW = new Date("2026-10-11T06:00:00Z");
// Wed 7 Oct 2026, 11:00 am IST = 05:30 UTC.
const VISIT = "2026-10-07T05:30:00Z";

describe("familyTime", () => {
  it("formats dates one way: no leading zero, three-letter months", () => {
    expect(familyDate(VISIT, { now: NOW })).toBe("Wed 7 Oct");
    expect(familyDate(VISIT, { weekday: false, now: NOW })).toBe("7 Oct");
    expect(familyDate("2026-09-03T05:30:00Z", { weekday: false, now: NOW })).toBe("3 Sep");
    expect(familyDate("2025-09-03T05:30:00Z", { weekday: false, now: NOW })).toBe("3 Sep 2025");
    expect(familyDate(null)).toBe("");
  });

  it("shows IST only for India or an unknown zone", () => {
    expect(familyTime(VISIT, "Asia/Kolkata", { now: NOW })).toBe("Wed 7 Oct, 11:00 am IST");
    expect(familyTime(VISIT, null, { now: NOW })).toBe("Wed 7 Oct, 11:00 am IST");
    expect(familyTime(VISIT, "Not/AZone", { now: NOW })).toBe("Wed 7 Oct, 11:00 am IST");
  });

  it("shows the family's own time with IST in brackets", () => {
    // London is BST (UTC+1) on 7 Oct.
    expect(familyTime(VISIT, "Europe/London", { now: NOW })).toBe("Wed 7 Oct, 6:30 am (11:00 am IST)");
    // New York (UTC-4): still the evening before.
    expect(familyTime(VISIT, "America/New_York", { now: NOW })).toBe("Wed 7 Oct, 1:30 am (11:00 am IST)");
    expect(familyTime("2026-10-07T02:00:00Z", "America/New_York", { now: NOW })).toBe(
      "Tue 6 Oct, 10:00 pm (Wed 7 Oct, 7:30 am IST)",
    );
    expect(familyClock(VISIT, "Europe/London")).toBe("6:30 am (11:00 am IST)");
    expect(familyClock(VISIT, "Asia/Kolkata")).toBe("11:00 am IST");
  });

  it("tidies dates inside stored text", () => {
    expect(tidyDates("Visit on Sat 03 Oct and 1 Sept")).toBe("Visit on Sat 3 Oct and 1 Sep");
  });

  it("spots scheduled notices posted after their date", () => {
    expect(isBackdatedSchedule("Care visit scheduled: Mon 7 Sep", "2026-10-07T10:00:00Z")).toBe(true);
    expect(isBackdatedSchedule("Care visit scheduled: Mon 12 Oct", "2026-10-07T10:00:00Z")).toBe(false);
    expect(isBackdatedSchedule("Care visit completed: Mon 7 Sep", "2026-10-07T10:00:00Z")).toBe(false);
    expect(isBackdatedSchedule("Care visit scheduled", "2026-10-07T10:00:00Z")).toBe(false);
  });
});

describe("familyWords", () => {
  it("swaps clinical terms for plain words", () => {
    expect(plainWords("Medication non-adherence")).toBe("Missed medicines");
    expect(plainWords("Unsafe toilet transfer")).toBe("Getting on and off the toilet safely");
    expect(plainWords("Support safer ambulation indoors and outdoors.")).toBe("Support safer walking indoors and outdoors.");
    expect(plainWords("Hourly ADL support")).toBe("Hourly daily activities support");
    expect(plainWords("Instrumental ADLs")).toBe("Household tasks");
    expect(plainWords("An Elder Care Manager (ECM) is recommended")).toBe("A care manager is recommended");
    expect(plainWords("Share plan with family/ECM")).toBe("Share plan with family/care manager");
    expect(plainWords("")).toBe("");
  });

  it("cleans photo captions", () => {
    expect(photoCaption("Home safety photo (hsa-1784559753603-l3qdo0e)")).toBe("Room photo");
    expect(photoCaption("Bathroom (hsa-1784559753603-l3qdo0e)")).toBe("Bathroom");
    expect(photoCaption("")).toBe("Room photo");
    expect(photoCaption("Kitchen")).toBe("Kitchen");
  });

  it("drops Context: lines", () => {
    expect(withoutContextLines("Context: Lakshmi\nAll well today.")).toBe("All well today.");
    expect(withoutContextLines("Context: Lakshmi")).toBe("");
    expect(withoutContextLines("All well.")).toBe("All well.");
  });
});

describe("familyStatusLine", () => {
  const checks = { mood: "ok", meds: "ok", food: "ok", mobility: "ok" } as Record<string, "ok" | "concern">;

  it("builds the one-line status", () => {
    const s = familyStatusLine({ elderFirst: "Lakshmi", lastVisitAt: VISIT, staffName: "Anita Rao", checks, now: NOW });
    expect(s.text).toBe("Lakshmi is well · last visit Wed 7 Oct by Anita · 4/4 checks OK");
    expect(s.tone).toBe("ok");
  });

  it("uses neutral wording when watching, and 'you' for the elder", () => {
    const s = familyStatusLine({ elderFirst: "Lakshmi", klStatus: "Watching", lastVisitAt: VISIT, now: NOW });
    expect(s.text).toBe("Your care team is keeping a close eye on Lakshmi · last visit Wed 7 Oct");
    expect(s.tone).toBe("watch");
    const me = familyStatusLine({ elderFirst: "Lakshmi", isSelf: true, level: "needs_attention", now: NOW });
    expect(me.text).toBe("Your care team is keeping a close eye on you · no visit yet");
    expect(familyStatusLine({ elderFirst: "Lakshmi", isSelf: true, now: NOW }).text).toBe("You are well · no visit yet");
  });

  it("counts concerns", () => {
    const s = familyStatusLine({ elderFirst: "Lakshmi", level: "urgent", checks: { ...checks, meds: "concern" }, now: NOW });
    expect(s.text).toBe("Lakshmi needs attention · no visit yet · 3/4 checks OK");
    expect(s.tone).toBe("alert");
  });
});

describe("requestStep", () => {
  it("maps request statuses to the tracker", () => {
    expect(requestStep({ status: "requested" })).toBe(0);
    expect(requestStep({ status: "requested", quoted_amount_minor: 150000 })).toBe(1);
    expect(requestStep({ status: "requested", payment_status: "awaiting_approval" })).toBe(1);
    expect(requestStep({ status: "confirmed" })).toBe(2);
    expect(requestStep({ status: "done" })).toBe(3);
    expect(requestStep({ status: "cancelled" })).toBeNull();
    expect(requestStep({ status: "declined" })).toBeNull();
  });
});

describe("familyPlan", () => {
  it("projects the score from open plan points, never 100", () => {
    expect(projectedScore(43, [{ score_gain: 30 }, { score_gain: 22 }, { score_gain: 10, status: "done" }])).toBe(95);
    expect(projectedScore(43, [{ score_gain: 20 }, { score_gain: 12 }])).toBe(75);
    expect(projectedScore(43, [])).toBeNull();
    expect(projectedScore(null, [{ score_gain: 5 }])).toBeNull();
  });

  it("adds price ranges into one total", () => {
    expect(parseRupeeRange("₹3,000–₹25,000")).toEqual([3000, 25000]);
    expect(parseRupeeRange("We'll quote")).toBeNull();
    expect(totalCostRange([{ estimated_cost: "₹3,000–₹25,000" }, { estimated_cost: "₹4,000–₹40,000" }, { estimated_cost: null }])).toBe(
      "₹7,000–₹65,000",
    );
    expect(totalCostRange([{ estimated_cost: "" }])).toBeNull();
  });
});
