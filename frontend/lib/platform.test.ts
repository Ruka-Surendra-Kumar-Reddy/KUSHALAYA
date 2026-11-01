import { describe, expect, it } from "vitest";

import {
  DEFAULT_VERTICAL,
  VERTICALS,
  normalizeVertical,
  verticalLabel,
} from "./platform";

describe("normalizeVertical", () => {
  it("returns known vertical ids unchanged", () => {
    expect(normalizeVertical("ELDER_CARE")).toBe(VERTICALS.ELDER_CARE);
    expect(normalizeVertical("SECURITY")).toBe(VERTICALS.SECURITY);
  });

  it("falls back to default for unknown or empty values", () => {
    expect(normalizeVertical(undefined)).toBe(DEFAULT_VERTICAL);
    expect(normalizeVertical(null)).toBe(DEFAULT_VERTICAL);
    expect(normalizeVertical("")).toBe(DEFAULT_VERTICAL);
    expect(normalizeVertical("NOT_A_VERTICAL")).toBe(DEFAULT_VERTICAL);
  });
});

describe("verticalLabel", () => {
  it("maps vertical ids to product labels", () => {
    expect(verticalLabel(VERTICALS.ELDER_CARE)).toBe("Elder Care");
    expect(verticalLabel(VERTICALS.SECURITY)).toBe("SecurityOps");
  });
});

/** Compile-time guard: select handlers must assign VerticalId, not raw string. */
describe("tenant form vertical typing", () => {
  it("accepts VerticalId from normalizeVertical (select onChange pattern)", () => {
    const simulateSelectChange = (raw: string) =>
      normalizeVertical(raw);

    const vertical = simulateSelectChange("HOUSEKEEPING");
    const form: { vertical: typeof vertical } = { vertical };
    expect(form.vertical).toBe(VERTICALS.HOUSEKEEPING);
  });
});
