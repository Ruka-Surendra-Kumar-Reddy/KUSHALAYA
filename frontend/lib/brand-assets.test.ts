import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { BRAND_ASSETS, BRAND_ASSET_SIZE, BRAND_ASSET_VERSION } from "./brand-assets";

/**
 * The logo files and the numbers describing them live apart, so they can drift:
 * resize a PNG and the `width`/`height` attributes reserve the wrong box, or
 * replace one without bumping the version and browsers keep the old mark for a
 * year (see the immutable cache rule in next.config.mjs). These read the files.
 */

/** Width and height out of a PNG's IHDR chunk, which is always first. */
function pngSize(file: string): { width: number; height: number } {
  const buf = readFileSync(join(process.cwd(), "public", file));
  expect(buf.subarray(1, 4).toString("ascii")).toBe("PNG");
  expect(buf.subarray(12, 16).toString("ascii")).toBe("IHDR");
  return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
}

const variants = Object.keys(BRAND_ASSETS) as (keyof typeof BRAND_ASSETS)[];

describe("brand assets", () => {
  it.each(variants)("%s declares the real pixel size of its file", (variant) => {
    const path = BRAND_ASSETS[variant].split("?")[0].replace(/^\//, "");
    expect(pngSize(path)).toEqual(BRAND_ASSET_SIZE[variant]);
  });

  it("versions every URL, so the year-long cache cannot serve a stale mark", () => {
    for (const variant of variants) {
      expect(BRAND_ASSETS[variant]).toContain(`?v=${BRAND_ASSET_VERSION}`);
    }
  });

  it("uses a version that changes when the files do", () => {
    // A date stamp, so a replaced asset gets a new URL just by bumping the day,
    // with an optional letter for a second release on the same day.
    expect(BRAND_ASSET_VERSION).toMatch(/^\d{8}[a-z]?$/);
  });
});
