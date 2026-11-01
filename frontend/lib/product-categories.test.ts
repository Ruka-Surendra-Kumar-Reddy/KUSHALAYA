import { describe, expect, it } from "vitest";
import { canonicalCategory, groupByCategory } from "./product-categories";

describe("canonicalCategory", () => {
  it("merges the two spellings", () => {
    expect(canonicalCategory("Bathroom Safety")).toBe("Bathroom");
    expect(canonicalCategory("Living Room")).toBe("Living room");
    expect(canonicalCategory("Kushalaya Services")).toBe("Service");
    expect(canonicalCategory("Service")).toBe("Service");
    expect(canonicalCategory("Wearables")).toBe("Wearable");
  });
  it("keeps unknown categories and blanks", () => {
    expect(canonicalCategory("Garden")).toBe("Garden");
    expect(canonicalCategory("")).toBe("");
  });
});

describe("groupByCategory", () => {
  it("groups merged names in editor order, uncategorised last", () => {
    const rows = [
      { n: 1, c: "Living Room" },
      { n: 2, c: "" },
      { n: 3, c: "Bathroom Safety" },
      { n: 4, c: "Bathroom" },
    ];
    const g = groupByCategory(rows, (r) => r.c);
    expect(g.map((x) => x.category)).toEqual(["Bathroom", "Living room", "No category"]);
    expect(g[0].items.map((r) => r.n)).toEqual([3, 4]);
  });
});
