import { test, expect } from "@playwright/test";
import {
  loginAsFamilyPortal,
  loginAsManager,
  loginAsTenantAdmin,
  sidebarNav,
} from "./helpers/auth";
import { FAMILY_ORIGIN } from "./helpers/hosts";

test.describe("Super admin", () => {
  // superadmin@safehomeops.com is not seeded locally and the multi-agency
  // /tenants pages were retired in the 2026-10 ops clean-up (lib/ops-retired.ts).
  test.skip(true, "No platform super admin account or tenant management any more");
  test("sees tenant management", async () => {});
});

test.describe("Agency manager", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsManager(page);
  });

  test("sees the Kushalaya ops menu, not retired or ElderCare links", async ({ page }) => {
    const nav = sidebarNav(page);
    for (const name of [/^Dashboard/, /^Clients/, /^Visits/, /^Assessments/, /^Team/]) {
      await expect(nav.getByRole("link", { name })).toBeVisible();
    }
    for (const href of ["/prospects", "/tenants", "/kushalaya/partners", "/kushalaya/pricing", "/elders", "/caregivers"]) {
      await expect(nav.locator(`a[href="${href}"]`)).toHaveCount(0);
    }
  });
});

test.describe("Tenant admin", () => {
  test("can open the assessment questions editor", async ({ page }) => {
    await loginAsTenantAdmin(page);
    await page.goto("/kushalaya/rubric");
    await expect(page.getByRole("heading", { name: "Assessment questions" })).toBeVisible();
  });
});

test.describe("Family portal", () => {
  test("family app loads dashboard on the family host", async ({ page }) => {
    await loginAsFamilyPortal(page);
    await expect(page).toHaveURL(`${FAMILY_ORIGIN}/dashboard`);
  });
});
