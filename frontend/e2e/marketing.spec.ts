import { test, expect } from "@playwright/test";
import { HYDRATION_WARNING, MARKETING_ORIGIN, watchConsole } from "./helpers/hosts";

// Marketing site on its local host (kushalaya.localhost, see lib/hosts.ts).
const PAGES: [string, RegExp][] = [
  ["/", /KushAlaya/],
  ["/packages", /^Packages/],
  ["/about", /^About us/],
  ["/contact", /^Contact us/],
  ["/blog", /blog/i],
];

test.describe("Marketing site", () => {
  for (const [path, title] of PAGES) {
    test(`${path} loads without console errors`, async ({ page }) => {
      const errors = watchConsole(page, [HYDRATION_WARNING]);
      const res = await page.goto(`${MARKETING_ORIGIN}${path}`);
      expect(res?.status()).toBe(200);
      await expect(page).toHaveTitle(title);
      await expect(page.locator("main.mk-main h1").first()).toBeVisible();
      await page.waitForLoadState("networkidle");
      expect(errors(), `console errors on ${path}`).toEqual([]);
    });
  }

  test("unknown path shows the branded 404", async ({ page }) => {
    const errors = watchConsole(page, [HYDRATION_WARNING, /status of 404/]);
    const res = await page.goto(`${MARKETING_ORIGIN}/no-such-page-e2e`);
    expect(res?.status()).toBe(404);
    await expect(page).toHaveTitle(/Page not found/);
    await expect(page.getByRole("heading", { name: /couldn.t find that page/i })).toBeVisible();
    expect(errors()).toEqual([]);
  });

  // Known bug: app/marketing/layout.tsx (REVEAL_BOOT) adds class "js" to
  // <html> before hydration, but <html> in app/layout.tsx has no
  // suppressHydrationWarning, so React logs a className mismatch (dev only).
  test("home page hydrates without a mismatch warning", async ({ page }) => {
    const errors = watchConsole(page);
    await page.goto(`${MARKETING_ORIGIN}/`);
    await page.waitForLoadState("networkidle");
    expect(errors().filter((e) => HYDRATION_WARNING.test(e))).toEqual([]);
  });
});
