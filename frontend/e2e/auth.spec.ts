import { test, expect } from "@playwright/test";
import { DEMO_USERS, mainContent, sidebar, uiLoginOps } from "./helpers/auth";
import { API_URL } from "./helpers/hosts";

test.describe("Authentication", () => {
  test("login page renders", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /Kushalaya/i })).toBeAttached();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: /Sign in/i })).toBeVisible();
  });

  test("manager signs in through the form and reaches the dashboard", async ({ page }) => {
    await uiLoginOps(page, DEMO_USERS.careManager);
    await expect(page).toHaveURL(/\/dashboard$/, { timeout: 60_000 });
    await expect(mainContent(page).getByRole("heading", { level: 1 })).toContainText(/Hello/);
    await expect(sidebar(page).getByRole("link", { name: /Clients/ })).toBeVisible();
    await expect(sidebar(page).getByRole("link", { name: /Visits/ })).toBeVisible();
  });

  test("wrong password shows an error on the form", async ({ page }) => {
    await uiLoginOps(page, { email: DEMO_USERS.careManager.email, password: "wrong-password" });
    await expect(page.getByRole("alert")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("family account is told to use the family portal", async ({ page }) => {
    await uiLoginOps(page, DEMO_USERS.elderPortal);
    await expect(page.locator(".ko-login-error")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("invalid credentials rejected by API", async ({ page }) => {
    const response = await page.request.post(`${API_URL}/api/v1/auth/login`, {
      data: { email: DEMO_USERS.careManager.email, password: "wrong-password" },
    });
    expect(response.status()).toBe(400);
    const body = await response.json();
    expect(String(body.detail).toLowerCase()).toContain("invalid");
  });

  test("signed-out visit to a staff page goes to /login", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login\?redirect=%2Fdashboard/);
  });
});
