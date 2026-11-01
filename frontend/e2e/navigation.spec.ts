import { test, expect } from "@playwright/test";
import { loginAsManager, mainContent, sidebarNav } from "./helpers/auth";

test.describe("Ops navigation", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsManager(page);
  });

  test("sidebar links open the main ops pages", async ({ page }) => {
    const main = mainContent(page);
    const steps: [RegExp, RegExp, string][] = [
      [/^Clients/, /\/kushalaya\/customers$/, "Clients"],
      [/^Visits/, /\/kushalaya\/visits$/, "Visits"],
      [/^Assessments/, /\/kushalaya\/assessments$/, "Assessments"],
      [/^Enquiries/, /\/kushalaya\/enquiries$/, "Enquiries"],
      [/^Dashboard/, /\/dashboard$/, "Hello"],
    ];
    for (const [link, url, heading] of steps) {
      await sidebarNav(page).getByRole("link", { name: link }).click();
      await expect(page).toHaveURL(url);
      await expect(main.getByRole("heading", { level: 1 })).toContainText(heading);
    }
  });

  test("retired pages send staff back to the dashboard", async ({ page }) => {
    for (const path of ["/prospects", "/tenants", "/kushalaya/partners"]) {
      await page.goto(path);
      await expect(page, path).toHaveURL(/\/dashboard$/);
    }
  });

  test("removed /livewell URLs show the branded 404", async ({ page }) => {
    const res = await page.goto("/livewell/visits");
    expect(res?.status()).toBe(404);
    await expect(page.getByRole("heading", { name: /couldn.t find that page/i })).toBeVisible();
  });
});
