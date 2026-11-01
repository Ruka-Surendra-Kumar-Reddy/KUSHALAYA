import { describe, expect, it } from "vitest";

import { brandifyDeep } from "./brandify";

describe("brandifyDeep", () => {
  it("leaves primitives other than strings unchanged", () => {
    expect(brandifyDeep(12)).toBe(12);
    expect(brandifyDeep(null)).toBeNull();
    expect(brandifyDeep(true)).toBe(true);
  });

  it("walks arrays and objects", () => {
    const input = {
      title: "LiveWell360 home",
      nested: { items: ["LiveWell360™ kit", 1] },
    };
    const out = brandifyDeep(input);
    expect(typeof out.title).toBe("string");
    expect(Array.isArray(out.nested.items)).toBe(true);
    expect(out.nested.items[1]).toBe(1);
  });
});
