import { test, expect } from "@playwright/test";
import { uiLoginFamily } from "./helpers/auth";
import { FAMILY_ORIGIN, watchConsole } from "./helpers/hosts";

// Family portal on its own host (family.localhost), signed in through the form.
test.describe("Family portal", () => {
  const pages: [string, RegExp][] = [
    ["/dashboard", /^Hello/],
    ["/safety", /^Score & plan$/],
    ["/plan", /Living improvement plan/],
    ["/services", /^Requests$/],
    ["/updates", /^Updates$/],
  ];

  test("sign-in, then home, safety, plan, requests and updates load cleanly", async ({ page, context }) => {
    const errors = watchConsole(page);
    await uiLoginFamily(page, context);

    for (const [path, heading] of pages) {
      await page.goto(`${FAMILY_ORIGIN}${path}`);
      await expect(page, path).toHaveURL(`${FAMILY_ORIGIN}${path}`);
      await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible({ timeout: 30_000 });
      await page.waitForLoadState("networkidle");
    }
    expect(errors(), "console errors on the family portal").toEqual([]);
  });

  test("menu links match the pages", async ({ page, context }) => {
    await uiLoginFamily(page, context);
    const nav = page.locator("nav.fh-nav");
    await expect(nav.locator('a[href="/services"]')).toContainText("Requests");
    await expect(nav.locator('a[href="/updates"]')).toContainText("Updates");
    await expect(nav.locator('a[href="/safety"]')).toContainText("Score & plan");
  });

  test("unknown path on the family host goes to the dashboard", async ({ page, context }) => {
    await uiLoginFamily(page, context);
    await page.goto(`${FAMILY_ORIGIN}/no-such-page`);
    await expect(page).toHaveURL(`${FAMILY_ORIGIN}/dashboard`);
    await expect(page.getByRole("heading", { level: 1, name: /^Hello/ })).toBeVisible();
    await page.waitForLoadState("networkidle");
  });
});
