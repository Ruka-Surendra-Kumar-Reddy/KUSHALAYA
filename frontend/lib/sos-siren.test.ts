import { describe, expect, it } from "vitest";
import { PRESSED_HERE_MS, SIREN_REPEAT_MS, WAIL_SECONDS, dueKeys, pressedAtLabel, quietHere, sirenKey, telHref, wailSchedule } from "./sos-siren";

describe("sos siren helpers", () => {
  it("keys an escalation as a new alert, not a confirmation", () => {
    expect(sirenKey({ id: 4, escalated: false })).toBe("4");
    expect(sirenKey({ id: 4, escalated: true })).toBe("4:esc");
  });

  it("plays once per new alert and repeats every 2 minutes", () => {
    const item = { id: 1, escalated: false };
    const key = sirenKey(item);
    expect(dueKeys([item], {}, 1000)).toEqual([key]);
    expect(dueKeys([item], { [key]: 1000 }, 1000 + 60_000)).toEqual([]);
    expect(dueKeys([item], { [key]: 1000 }, 1000 + SIREN_REPEAT_MS)).toEqual([key]);
    expect(dueKeys([{ ...item, escalated: true }], { [key]: 1000 }, 2000)).toEqual(["1:esc"]);
  });

  it("builds an ambulance hooter: two slow wails then a fast yelp, within the sound length", () => {
    const s = wailSchedule();
    expect(s[0]).toEqual({ t: 0, f: 650 });
    expect(s[1]).toEqual({ t: 0.9, f: 1400 }); // slow wail up
    expect(s[5].t - s[4].t).toBeCloseTo(0.12, 3); // fast yelp
    expect(s.length).toBe(1 + 2 * 2 + 6 * 2);
    expect(s[s.length - 1].t).toBeLessThanOrEqual(WAIL_SECONDS);
  });

  it("makes safe tel links", () => {
    expect(telHref("+91 98765 43210")).toBe("tel:+919876543210");
    expect(telHref("040-2345 6789")).toBe("tel:04023456789");
    expect(telHref("")).toBe("");
    expect(telHref("call me")).toBe("");
  });

  it("labels the press time", () => {
    expect(pressedAtLabel("not a date")).toBe("");
    expect(pressedAtLabel("2026-10-26T05:12:00+00:00")).not.toBe("");
  });
});

describe("per device (27 Oct)", () => {
  it("only the device that pressed stays quiet, and only for a while", () => {
    const now = 1_000_000;
    expect(quietHere({ pressed_by_me: true }, now - 5_000, now)).toBe(true);
    expect(quietHere({ pressed_by_me: true }, null, now)).toBe(false); // another device of the same account
    expect(quietHere({ pressed_by_me: false }, now - 5_000, now)).toBe(false); // someone else's SOS
    expect(quietHere({ pressed_by_me: true }, now - PRESSED_HERE_MS - 1, now)).toBe(false); // pressed long ago
  });
});
