import { describe, expect, it } from "vitest";

import { formatInrLakhs } from "./executive";

describe("formatInrLakhs", () => {
  it("formats with lakhs suffix", () => {
    expect(formatInrLakhs(1.5)).toMatch(/Lakhs$/);
    expect(formatInrLakhs(0)).toMatch(/Lakhs$/);
    expect(formatInrLakhs(12.345)).toMatch(/12\.35|12\.345/);
  });
});
