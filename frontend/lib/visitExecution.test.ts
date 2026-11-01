import { describe, expect, it } from "vitest";

import { noteTypeLabel } from "./visitExecution";

describe("noteTypeLabel", () => {
  it.each([
    ["GENERAL", "General update"],
    ["HANDOVER", "Handover to family"],
    ["CONCERN", "Concern / watch item"],
    ["CUSTOM_TYPE", "CUSTOM TYPE"],
  ] as const)("%s", (value, label) => {
    expect(noteTypeLabel(value)).toBe(label);
  });
});
