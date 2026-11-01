import { describe, expect, it } from "vitest";
import { jobWhen } from "./jobs";

describe("jobWhen", () => {
  it("shows India time in 12-hour form", () => {
    // 19:05 UTC = 12:35 am next day in India.
    expect(jobWhen("2026-10-07T19:05:00Z")).toBe("Thu 8 Oct, 12:35 am");
    expect(jobWhen("2026-10-08T08:30:00Z")).toBe("Thu 8 Oct, 2:00 pm");
  });

  it("says when there is no time", () => {
    expect(jobWhen(null)).toBe("Time to be confirmed");
  });
});
