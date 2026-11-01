import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Guard against pre-rename brand strings reaching users raw.
 *
 * `LiveWell360` is the authoring token and is rewritten at runtime by
 * withPublicBrand() / brandifyDeep(), so it is fine in source copy. What leaks
 * is the *old* product name "SafeHome 360" and bare "LiveWell" (no 360), which
 * nothing rewrites. These files were cleaned in Sept 2026; a regression here
 * means a string was added that bypasses the token system.
 *
 * Module paths (`@/lib/livewell/...`, `./livewell-...`) are lowercase and never
 * match the case-sensitive pattern; wire ids such as `livewell_ble` likewise.
 */

const LEAK = /SafeHome 360|SafeHome quote|\bLiveWell\b(?!360)/g;

/** Rendered-string sources that were fixed; add to this list, never remove. */
const GUARDED_FILES = [
  "app/(app)/kushalaya/suppliers/page.tsx",
  "app/(app)/kushalaya/pricing/page.tsx",
  "app/(app)/settings/page.tsx",
  "app/not-found.tsx",
  "components/livewell/IotDevicesAdminPanel.tsx",
  "components/livewell/ProductQuoteDraftPanel.tsx",
  "components/livewell/ProductShowcase.tsx",
  "components/livewell/RecommendationChatLaunchCard.tsx",
  "components/livewell/RubricAdminEditor.tsx",
  "components/livewell/RubricSourcesLegend.tsx",
  "components/livewell/ScoringGuide.tsx",
  "components/livewell/SuppliersAdminEditor.tsx",
  "lib/livewell/build-purchase-order.ts",
  "lib/livewell/catalogApi.ts",
  "lib/livewell/improvement-plan.ts",
  "lib/livewell/quote-report.ts",
  "lib/livewell/report-visualizations.ts",
  "lib/livewell/rubric-sources.ts",
  "lib/livewell/safehome360-rubric.ts",
  "lib/livewell/supplier-workbook.ts",
  "lib/livewell/syncProspect.ts",
  "lib/public-brand.ts",
  "components/marketing/KushLifeMarketingPage.tsx",
  "components/marketing/EnquiryForm.tsx",
  "components/ops/LeadFunnel.tsx",
  "app/(app)/settings/website/page.tsx",
  "lib/marketing/site-config.ts",
];

/**
 * Exact substrings that are allowed to match: the token's own documentation
 * and alias tables in lib/public-brand.ts. Keep this list short and literal.
 */
const ALLOWLIST = [
  // lib/public-brand.ts — alias table that maps the OLD names to the brand.
  '"safehome 360"',
  '"safehome 360™"',
  "resolvePortalBrandTitle",
];

function leaksIn(file: string): string[] {
  const text = readFileSync(join(process.cwd(), file), "utf8");
  const found: string[] = [];
  for (const [index, line] of text.split("\n").entries()) {
    if (ALLOWLIST.some((ok) => line.includes(ok))) continue;
    if (line.match(LEAK)) found.push(`${file}:${index + 1}: ${line.trim()}`);
  }
  return found;
}

describe("brand leaks", () => {
  it.each(GUARDED_FILES)("%s has no raw SafeHome 360 / bare LiveWell text", (file) => {
    expect(leaksIn(file)).toEqual([]);
  });

  it("the pattern accepts the authoring token and module paths", () => {
    expect("LiveWell360 Assessment".match(LEAK)).toBeNull();
    expect('import x from "@/lib/livewell/catalog"'.match(LEAK)).toBeNull();
    expect('value="livewell_ble"'.match(LEAK)).toBeNull();
    expect("your LiveWell catalog".match(LEAK)).not.toBeNull();
    expect("SafeHome 360™ suppliers".match(LEAK)).not.toBeNull();
    expect("SafeHome quote — Lakshmi".match(LEAK)).not.toBeNull();
  });
});
