import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { BRAND_INLINE, BRAND_INLINE_SIZE } from "./brand-inline";

/**
 * lib/brand-inline.ts is generated from public/brand by
 * scripts/gen-brand-inline.mjs. Replace a PNG without re-running it and the
 * page keeps painting the old mark, so this compares the two byte for byte.
 */

const FILES = {
  header: "brand/kushalaya-header.png",
  lockup: "brand/kushalaya-lockup.png",
} as const;

const variants = Object.keys(FILES) as (keyof typeof FILES)[];

describe("inline brand marks", () => {
  it.each(variants)("%s is the current file in public/brand", (variant) => {
    const file = readFileSync(join(process.cwd(), "public", FILES[variant]));
    expect(BRAND_INLINE[variant]).toBe(`data:image/png;base64,${file.toString("base64")}`);
  });

  it.each(variants)("%s declares the real pixel size", (variant) => {
    const file = readFileSync(join(process.cwd(), "public", FILES[variant]));
    expect(file.subarray(12, 16).toString("ascii")).toBe("IHDR");
    expect(BRAND_INLINE_SIZE[variant]).toEqual({
      width: file.readUInt32BE(16),
      height: file.readUInt32BE(20),
    });
  });

  it("stays small enough to ride inside every HTML response", () => {
    // Inlining trades a request for HTML bytes; past this the trade is a loss.
    for (const variant of variants) {
      expect(BRAND_INLINE[variant].length).toBeLessThan(40_000);
    }
  });
});
