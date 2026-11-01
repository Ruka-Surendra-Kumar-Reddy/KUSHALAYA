import { test } from "@playwright/test";
import { auditAllSidebarLinks } from "./helpers/nav-audit";
import { loginAsCareAdmin, loginAsManager } from "./helpers/auth";

test.describe.configure({ timeout: 180_000 });

test.describe("Sidebar links", () => {
  test("tenant admin: every sidebar link loads without API errors", async ({ page }) => {
    await loginAsCareAdmin(page);
    await auditAllSidebarLinks(page);
  });

  test("manager: every sidebar link loads without API errors", async ({ page }) => {
    await loginAsManager(page);
    await auditAllSidebarLinks(page);
  });
});

test.describe("Super admin sidebar links", () => {
  test.skip(true, "No platform super admin account locally; /tenants and the workforce marketplace are retired");
  test("every sidebar link loads or shows tenant gate", async () => {});
});
