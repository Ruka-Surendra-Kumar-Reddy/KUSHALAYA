import { BrowserContext, Page } from "@playwright/test";

/**
 * Local hosts only (lib/hosts.ts lists the *.localhost names next dev serves).
 * The host decides the site: 127.0.0.1 is the ops portal, family.localhost the
 * family portal, kushalaya.localhost the marketing site. Never point these at
 * production.
 */
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8010";
export const OPS_ORIGIN = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3010";

const port = new URL(OPS_ORIGIN).port || "3010";
export const FAMILY_ORIGIN = `http://family.localhost:${port}`;
export const MARKETING_ORIGIN = `http://kushalaya.localhost:${port}`;

for (const origin of [API_URL, OPS_ORIGIN]) {
  const host = new URL(origin).hostname;
  if (!["127.0.0.1", "localhost"].includes(host) && !host.endsWith(".localhost")) {
    throw new Error(`E2E refuses to run against a non-local host: ${origin}`);
  }
}

/**
 * The family and caregiver hosts call /api on their own origin (lib/api.ts
 * getApiUrl); nginx forwards that to the API in production. next dev has no
 * such proxy, so the tests forward it to the local API.
 */
export async function proxyApiLikeNginx(context: BrowserContext, origin: string) {
  await context.route(`${origin}/api/**`, async (route) => {
    const url = route.request().url().replace(origin, API_URL);
    try {
      const response = await route.fetch({ url });
      await route.fulfill({ response });
    } catch (err) {
      // A request still in flight when the test ends: the page is gone.
      if (!/has been closed/.test(String(err))) throw err;
    }
  });
}

/**
 * Collect console errors and uncaught page errors. Returns a function that
 * gives the messages seen so far, minus the ones matched by `ignore`.
 */
export function watchConsole(page: Page, ignore: RegExp[] = []) {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
  return () => errors.filter((e) => !ignore.some((re) => re.test(e)));
}

/**
 * React dev-mode hydration warning. Kept out of the per-page checks and
 * asserted on its own in marketing.spec.ts, so one known bug does not hide
 * other console errors.
 */
export const HYDRATION_WARNING = /did not match|Hydration failed|hydrat/i;
