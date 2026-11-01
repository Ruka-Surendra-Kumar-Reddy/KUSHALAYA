import { test, expect } from "@playwright/test";
import { loginAsManager, mainContent } from "./helpers/auth";

// Read-only walk through the main ops pages as the demo care manager.
test.describe("Ops portal main flows", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsManager(page);
  });

  test("dashboard shows the run sheet", async ({ page }) => {
    const main = mainContent(page);
    await expect(main.getByRole("heading", { name: "Today's run sheet" })).toBeVisible();
    await expect(main.locator("#dash-attn")).toBeVisible();
  });

  test("clients list opens a client page", async ({ page }) => {
    await page.goto("/kushalaya/customers");
    const main = mainContent(page);
    await expect(main.getByRole("heading", { level: 1, name: "Clients" })).toBeVisible();
    await main.getByRole("button", { name: "All", exact: true }).click();
    const client = main.locator('a[href^="/kushalaya/customers/"]').first();
    await expect(client).toBeVisible();
    const href = await client.getAttribute("href");
    await client.click();
    await expect(page).toHaveURL(new RegExp(`${href}$`));
    await expect(main.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(main.getByRole("heading", { level: 1 })).not.toHaveText(/^Clients$|not found/i);
  });

  test("visits / schedule page loads", async ({ page }) => {
    await page.goto("/kushalaya/visits");
    const main = mainContent(page);
    await expect(main.getByRole("heading", { level: 1, name: "Visits" })).toBeVisible();
    await expect(main.locator(".error-text")).toHaveCount(0);
  });

  test("assessments list loads", async ({ page }) => {
    await page.goto("/kushalaya/assessments");
    const main = mainContent(page);
    await expect(main.getByRole("heading", { level: 1, name: "Assessments" })).toBeVisible();
    await expect(main.getByRole("button", { name: "+ New assessment" })).toBeVisible();
    await expect(main.getByRole("heading", { name: "Assigned assessments" })).toBeVisible();
  });
});
