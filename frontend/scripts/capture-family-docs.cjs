/**
 * Capture family portal screenshots for docs/livewell/FAMILY_PORTAL_USER_GUIDE.md
 *
 *   cd frontend
 *   node scripts/capture-family-docs.cjs
 */
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const BASE = process.env.FAMILY_DOC_BASE || "https://ops.kushalaya.com";
const EMAIL = process.env.FAMILY_DOC_EMAIL || "lakshmi.family@sunrise-care.example";
const PASS = process.env.FAMILY_DOC_PASS || "demo1234";
const OUT = path.resolve(__dirname, "../../docs/livewell/images/family");

const AFTER_LOGIN = [
  { name: "02-home", path: "/livewell/family/dashboard", wait: /Independence Score|Hello,/i },
  { name: "03-schedule", path: "/livewell/family/schedule", wait: /Schedule|Request|visit/i },
  { name: "04-updates", path: "/livewell/family/updates", wait: /Updates|timeline|Care/i },
  { name: "05-more", path: "/livewell/family/more", wait: /Family circle|Independence Score|More/i },
  { name: "06-alerts-sos", path: "/livewell/family/alerts", wait: /Alert|SOS|unread/i },
  { name: "07-circle", path: "/livewell/family/circle", wait: /circle|Invite|Family/i },
  { name: "08-plan", path: "/livewell/family/plan", wait: /plan|Priorit|Living/i },
  { name: "09-safety-score", path: "/livewell/family/safety", wait: /Independence Score|Score|domain/i },
];

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();

  async function shot(name) {
    const file = path.join(OUT, `${name}.png`);
    await page.waitForTimeout(500);
    await page.screenshot({ path: file, fullPage: true });
    console.log("wrote", path.basename(file), "url=", page.url());
  }

  await page.goto(`${BASE}/kushalaya/family/login`, {
    waitUntil: "domcontentloaded",
    timeout: 90000,
  });
  await page.waitForSelector('input[type="email"]');
  await shot("01-login");

  await page.fill('input[type="email"]', EMAIL);
  await page.fill('input[type="password"]', PASS);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/livewell/family/dashboard**", { timeout: 60000 });
  await page.waitForSelector("text=Independence Score", { timeout: 30000 });

  for (const item of AFTER_LOGIN) {
    await page.goto(`${BASE}${item.path}`, {
      waitUntil: "domcontentloaded",
      timeout: 90000,
    });
    try {
      await page.waitForFunction(
        (reSrc) => new RegExp(reSrc, "i").test(document.body?.innerText || ""),
        item.wait.source,
        { timeout: 20000 },
      );
    } catch {
      console.log("wait soft-fail for", item.name);
    }
    await page.waitForTimeout(800);
    await shot(item.name);
  }

  // Digests (extra important)
  await page.goto(`${BASE}/livewell/family/digests`, {
    waitUntil: "domcontentloaded",
    timeout: 90000,
  });
  await page.waitForTimeout(1000);
  await shot("11-digests");

  // Multi-elder Viewing (Arjun)
  await context.clearCookies();
  await page.goto(`${BASE}/kushalaya/family/login`, {
    waitUntil: "domcontentloaded",
    timeout: 90000,
  });
  await page.evaluate(() => {
    try {
      localStorage.clear();
      sessionStorage.clear();
    } catch (_) {}
  });
  await page.fill('input[type="email"]', "arjun.family@sunrise-care.example");
  await page.fill('input[type="password"]', PASS);
  await page.click('button[type="submit"]');
  try {
    await page.waitForURL("**/livewell/family/**", { timeout: 60000 });
    await page.goto(`${BASE}/livewell/family/dashboard`, {
      waitUntil: "domcontentloaded",
      timeout: 90000,
    });
    await page.waitForTimeout(1500);
    if ((await page.locator(".home-safety-family-elder-switch").count()) > 0) {
      await shot("10-multi-elder-viewing");
    } else {
      console.log("No Viewing switcher — skip 10-multi-elder-viewing");
      await shot("10-home-arjun");
    }
  } catch (e) {
    console.log("Arjun shot skipped:", e.message);
  }

  await browser.close();
  console.log("done →", OUT);
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
