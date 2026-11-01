import { expect, Page } from "@playwright/test";

import { mainContent, sidebarNav } from "./auth";

const API_ERROR_PATTERNS = [
  /tenant_id is required/i,
  /Tenant context required/i,
  /Internal Server Error/i,
];

export type SidebarLink = { href: string; label: string };

/** Unique sidebar menu links in DOM order (admin shell only). */
export async function collectSidebarLinks(page: Page): Promise<SidebarLink[]> {
  const links = sidebarNav(page).locator('a[href^="/"]');
  const count = await links.count();
  const seen = new Set<string>();
  const result: SidebarLink[] = [];

  for (let i = 0; i < count; i++) {
    const link = links.nth(i);
    const href = await link.getAttribute("href");
    if (!href || seen.has(href)) continue;
    seen.add(href);
    const label = ((await link.innerText()) || href).trim();
    result.push({ href, label });
  }
  return result;
}

export async function assertMainContentHealthy(page: Page) {
  const main = mainContent(page);
  await expect(main).toBeVisible({ timeout: 30_000 });

  const body = await main.innerText();
  for (const pattern of API_ERROR_PATTERNS) {
    expect(body, `Unexpected API error on ${page.url()}`).not.toMatch(pattern);
  }

  const errorEl = main.locator(".error-text");
  if ((await errorEl.count()) > 0) {
    const errText = await errorEl.first().innerText();
    for (const pattern of API_ERROR_PATTERNS) {
      expect(errText, `Error banner on ${page.url()}`).not.toMatch(pattern);
    }
  }

  await expect(
    main.getByRole("heading").first(),
    `Tenant admin page missing heading: ${page.url()}`,
  ).toBeVisible();
}

async function openAppRoute(page: Page, href: string) {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      await page.goto(href, {
        waitUntil: "domcontentloaded",
        timeout: 60_000,
      });
      return;
    } catch (err) {
      const msg = String(err);
      if (attempt < 2 && msg.includes("ERR_ABORTED")) {
        await page.waitForTimeout(300);
        continue;
      }
      throw err;
    }
  }
}

export async function auditAllSidebarLinks(page: Page) {
  const links = await collectSidebarLinks(page);
  expect(links.length).toBeGreaterThan(0);

  for (const link of links) {
    await openAppRoute(page, link.href);
    await expect(page, `${link.label} should not bounce away`).toHaveURL(
      new RegExp(`${link.href.replace(/[?]/g, "\?")}`),
    );
    await mainContent(page).waitFor({ state: "visible", timeout: 30_000 });
    await assertMainContentHealthy(page);
  }
}
