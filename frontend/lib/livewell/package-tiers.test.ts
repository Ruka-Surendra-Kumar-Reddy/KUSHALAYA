import { describe, expect, it } from "vitest";

import { getPackageTierScope, solutionIdsForPackageTiers } from "./package-tiers";

describe("package tiers", () => {
  const ids = ["a", "b", "c", "d", "e", "f"];

  it("resolves highest selected tier", () => {
    expect(getPackageTierScope(["essential"])).toBe("essential");
    expect(getPackageTierScope(["essential", "comfort"])).toBe("comfort");
    expect(getPackageTierScope(["essential", "premium"])).toBe("premium");
  });

  it("scopes solution lists progressively", () => {
    expect(solutionIdsForPackageTiers(ids, ["essential"])).toEqual(["a", "b"]);
    expect(solutionIdsForPackageTiers(ids, ["comfort"])).toEqual(["a", "b", "c", "d"]);
    expect(solutionIdsForPackageTiers(ids, ["premium"])).toEqual(ids);
    expect(solutionIdsForPackageTiers(ids, ["essential", "comfort"])).toEqual([
      "a",
      "b",
      "c",
      "d",
    ]);
  });
});
