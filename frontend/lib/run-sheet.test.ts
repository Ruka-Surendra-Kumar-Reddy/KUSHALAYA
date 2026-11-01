import { describe, expect, it } from "vitest";
import { arrivalAt, hoursWaiting, isReplyOverdue, isStaleCheckIn, plural, staleLabel, startedAt, waitLabel } from "./run-sheet";

const NOW = new Date("2026-10-11T12:00:00Z").getTime();
const hoursAgo = (h: number) => new Date(NOW - h * 3_600_000).toISOString();

describe("isStaleCheckIn", () => {
  it("flags a check-in older than 12 hours", () => {
    expect(isStaleCheckIn({ status: "checked_in", checked_in_at: hoursAgo(13) }, NOW)).toBe(true);
  });
  it("does not flag a recent check-in", () => {
    expect(isStaleCheckIn({ status: "checked_in", checked_in_at: hoursAgo(2) }, NOW)).toBe(false);
  });
  it("ignores finished or scheduled visits", () => {
    expect(isStaleCheckIn({ status: "completed", checked_in_at: hoursAgo(48) }, NOW)).toBe(false);
    expect(isStaleCheckIn({ status: "scheduled", scheduled_at: hoursAgo(48) }, NOW)).toBe(false);
  });
  it("falls back to the booked time when no arrival time is stored", () => {
    expect(isStaleCheckIn({ status: "on_the_way", scheduled_at: hoursAgo(20) }, NOW)).toBe(true);
    expect(isStaleCheckIn({ status: "checked_in" }, NOW)).toBe(false);
  });
});

describe("reply waiting", () => {
  it("counts whole hours and flags 24 h or more", () => {
    expect(hoursWaiting(hoursAgo(5.5), NOW)).toBe(5);
    expect(isReplyOverdue(hoursAgo(23), NOW)).toBe(false);
    expect(isReplyOverdue(hoursAgo(25), NOW)).toBe(true);
    expect(isReplyOverdue(null, NOW)).toBe(false);
  });
  it("labels hours then days", () => {
    expect(waitLabel(5)).toBe("5 h");
    expect(waitLabel(24)).toBe("1 day");
    expect(waitLabel(120)).toBe("5 days");
  });
});

describe("plural", () => {
  it("uses the singular for one", () => {
    expect(plural(1, "caregiver")).toBe("1 caregiver");
    expect(plural(3, "caregiver")).toBe("3 caregivers");
    expect(plural(0, "visit")).toBe("0 visits");
  });
});

describe("rebooked visits", () => {
  const T = Date.parse("2026-10-12T00:00:00Z");
  const ago = (h: number) => new Date(T - h * 3_600_000).toISOString();
  const rebooked = { status: "checked_in", scheduled_at: ago(88), checked_in_at: ago(134) };
  it("never shows an arrival days before the booking", () => {
    expect(arrivalAt(rebooked)).toBeNull();
    expect(startedAt(rebooked)).toBe(rebooked.scheduled_at);
  });
  it("keeps a normal or slightly early arrival", () => {
    expect(arrivalAt({ status: "checked_in", scheduled_at: ago(10), checked_in_at: ago(11) })).toBe(ago(11));
  });
  it("labels stale visits the same everywhere", () => {
    expect(staleLabel(rebooked, T)).toBe("Not closed · 3 days");
    expect(staleLabel({ status: "checked_in", checked_in_at: ago(14) }, T)).toBe("Not closed · 14 h");
  });
});
