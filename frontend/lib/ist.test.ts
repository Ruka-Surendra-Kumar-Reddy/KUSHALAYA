import { describe, expect, it } from "vitest";
import { dateTimeIST, formatIST, greetingIST, timeIST } from "./ist";

describe("greetingIST", () => {
  it("uses India time, not the device clock", () => {
    // 19:00 UTC = 00:30 IST
    expect(greetingIST(new Date("2026-10-11T19:00:00Z"))).toBe("Good night");
    expect(greetingIST(new Date("2026-10-12T03:00:00Z"))).toBe("Good morning");
    expect(greetingIST(new Date("2026-10-12T09:00:00Z"))).toBe("Good afternoon");
    expect(greetingIST(new Date("2026-10-12T13:00:00Z"))).toBe("Good evening");
  });
});

describe("API timestamps without a zone are UTC", () => {
  it("shows 07:11 UTC as 12:41 pm IST, with or without a Z", () => {
    expect(timeIST("2026-10-28T07:11:00")).toBe("12:41 pm");
    expect(timeIST("2026-10-28T07:11:00.123456")).toBe("12:41 pm");
    expect(timeIST("2026-10-28T07:11:00+00:00")).toBe("12:41 pm");
    expect(timeIST("2026-10-28T12:41:00+05:30")).toBe("12:41 pm");
    expect(dateTimeIST("2026-10-28T20:00:00")).toContain("29 Oct");
    expect(formatIST("2026-10-28T07:11:00")).toMatch(/12:41\s?pm IST/i);
  });
});
