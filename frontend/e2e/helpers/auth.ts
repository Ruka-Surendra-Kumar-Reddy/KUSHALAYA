import { BrowserContext, Page, expect } from "@playwright/test";

import { API_URL, FAMILY_ORIGIN, OPS_ORIGIN, proxyApiLikeNginx } from "./hosts";

export const DEMO_PASSWORD = "demo1234";

/**
 * Local demo accounts (backend seed, docs/DEMO_USERS.md). There is no
 * platform super admin locally — `superadmin@safehomeops.com` is not seeded,
 * and the multi-agency /tenants pages were retired (lib/ops-retired.ts).
 */
export const DEMO_USERS = {
  careManager: {
    email: "manager@sunrise-care.example",
    password: DEMO_PASSWORD,
    role: "CARE_MANAGER",
  },
  tenantAdmin: {
    email: "admin@sunrise-care.example",
    password: DEMO_PASSWORD,
    role: "TENANT_ADMIN",
  },
  caregiver: {
    email: "anita.caregiver@sunrise-care.example",
    password: DEMO_PASSWORD,
    role: "CAREGIVER",
  },
  elderPortal: {
    email: "lakshmi.family@sunrise-care.example",
    password: DEMO_PASSWORD,
    role: "ELDER_PORTAL",
  },
} as const;

type DemoUser = { email: string; password: string };

/** Ops portal sidebar (components/AppShell -> aside.ko-sidebar). */
export function sidebar(page: Page) {
  return page.locator("aside.ko-sidebar");
}

/** Menu items inside the sidebar (excludes the Assessor / Family portal links). */
export function sidebarNav(page: Page) {
  return sidebar(page).locator("nav.ko-nav");
}

/** Main content area of the ops shell. */
export function mainContent(page: Page) {
  return page.locator("main.ko-content");
}

/** Family portal side menu. */
export function familyNav(page: Page) {
  return page.locator("nav.fh-nav");
}

/** API token for a demo user (for read-only checks and test-data clean-up). */
export async function apiToken(page: Page, user: DemoUser): Promise<string> {
  const response = await page.request.post(`${API_URL}/api/v1/auth/login`, {
    data: { email: user.email, password: user.password },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  return (await response.json()).access_token as string;
}

/**
 * Fast login: API sign-in, then the session is put in localStorage and the
 * `ks_portal` hint cookie is set (middleware sends staff pages to /login
 * without it). Use uiLogin* when the sign-in form itself is under test.
 */
export async function loginAs(page: Page, user: DemoUser, landingPath: string) {
  const response = await page.request.post(`${API_URL}/api/v1/auth/login`, {
    data: { email: user.email, password: user.password },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
  const data = await response.json();
  const auth = {
    email: data.email,
    role: data.role,
    tenant_id: data.tenant_id,
    elder_id: data.elder_id ?? null,
    customer_id: data.customer_id ?? data.elder_id ?? null,
    access_token: data.access_token,
    refresh_token: data.refresh_token,
  };
  const kind =
    data.role === "ELDER_PORTAL" ? "family" : data.role === "CAREGIVER" ? "caregiver" : "staff";

  await page.context().addCookies([
    { name: "ks_portal", value: kind, url: OPS_ORIGIN },
  ]);
  await page.addInitScript((stored) => {
    window.localStorage.setItem("sho_auth", JSON.stringify(stored));
    window.localStorage.removeItem("eco_auth");
    window.localStorage.setItem("sho_admin_locale", "en");
  }, auth);

  await page.goto(landingPath);
}

export async function loginAsManager(page: Page) {
  await loginAs(page, DEMO_USERS.careManager, "/dashboard");
  await expect(mainContent(page).getByRole("heading", { level: 1 })).toContainText(
    /Hello|Dashboard/,
    { timeout: 30_000 },
  );
}

export async function loginAsTenantAdmin(page: Page) {
  await loginAs(page, DEMO_USERS.tenantAdmin, "/dashboard");
  await expect(mainContent(page).getByRole("heading", { level: 1 })).toBeVisible({
    timeout: 30_000,
  });
}

export async function loginAsCareAdmin(page: Page) {
  await loginAsTenantAdmin(page);
}

/** Staff / caregiver sign-in through the real form on the ops host. */
export async function uiLoginOps(page: Page, user: DemoUser) {
  await page.goto(`${OPS_ORIGIN}/login`);
  await page.locator("#email").fill(user.email);
  await page.locator("#password").fill(user.password);
  await page.getByRole("button", { name: /Sign in/i }).click();
}

/**
 * Family sign-in through the real form on the family host
 * (family.localhost:3010). In production nginx proxies /api on that host;
 * next dev does not, so the test does it (see proxyApiLikeNginx).
 */
export async function uiLoginFamily(page: Page, context: BrowserContext) {
  await proxyApiLikeNginx(context, FAMILY_ORIGIN);
  await page.goto(`${FAMILY_ORIGIN}/login`);
  await page.locator("#family-email").fill(DEMO_USERS.elderPortal.email);
  await page.locator("#family-password").fill(DEMO_USERS.elderPortal.password);
  await page.getByRole("button", { name: /Sign in/i }).click();
  await expect(page).toHaveURL(`${FAMILY_ORIGIN}/dashboard`, { timeout: 60_000 });
}

export async function loginAsFamilyPortal(page: Page) {
  await uiLoginFamily(page, page.context());
  await expect(page.getByRole("heading", { name: /^Hello/ })).toBeVisible({
    timeout: 30_000,
  });
}
