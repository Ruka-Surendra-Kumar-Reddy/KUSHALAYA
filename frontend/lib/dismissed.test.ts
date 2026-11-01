import { describe, expect, it } from "vitest";
import { DISMISS_DAYS, isDismissed } from "./dismissed";

const DAY = 24 * 60 * 60 * 1000;

describe("isDismissed", () => {
  const now = Date.UTC(2026, 9, 28);
  it("shows a banner that was never closed", () => {
    expect(isDismissed(null, now)).toBe(false);
  });
  it("hides it for DISMISS_DAYS after closing, then it comes back", () => {
    expect(isDismissed(now - DAY, now)).toBe(true);
    expect(isDismissed(now - (DISMISS_DAYS * DAY - 1), now)).toBe(true);
    expect(isDismissed(now - DISMISS_DAYS * DAY, now)).toBe(false);
  });
  it("ignores a closed-at time in the future (clock changed)", () => {
    expect(isDismissed(now + DAY, now)).toBe(false);
  });
});
