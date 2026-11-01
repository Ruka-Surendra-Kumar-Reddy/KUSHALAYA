import { describe, expect, it } from "vitest";

import { benchCategoryLabel } from "./workforce";

describe("benchCategoryLabel", () => {
  it("returns code when translator missing or unused", () => {
    expect(benchCategoryLabel("READY")).toBe("READY");
    expect(benchCategoryLabel("TRAINING", (key) => key)).toBe("TRAINING");
  });

  it("uses translator when it returns a different label", () => {
    expect(benchCategoryLabel("READY", (key) => (key.endsWith("READY") ? "Ready" : key))).toBe(
      "Ready",
    );
  });
});
