import { chromium } from "playwright";

const OUT = "C:/Users/ASUS/AppData/Local/Temp/claude/c--Users-ASUS-Downloads-SafeHomeOps-source-SafeHomeOps/e6eaf14d-0891-4ca1-9079-bfc5fd6157a8/scratchpad/shots";
const WEB = "http://localhost:3010";
const STEP = process.argv[2] || "all";
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

const browser = await chromium.launch();

async function sectionShots() {
  for (const w of [390, 768, 1440]) {
    const page = await browser.newPage({ viewport: { width: w, height: w === 390 ? 844 : 1000 } });
    await page.goto(`${WEB}/marketing/packages`, { waitUntil: "networkidle", timeout: 120000 });
    const sec = page.locator("#pay-as-you-go");
    await sec.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);
    await sec.screenshot({ path: `${OUT}/payg-${w}.png` });
    { const b = sec.getByRole("button", { name: "Physiotherapy sessions" }); await b.evaluate((e) => e.scrollIntoView({ block: "center" })); await b.click(); }
    const sheet = page.locator(".mk-buy");
    await sheet.waitFor();
    const need = await sheet.locator("select").first().inputValue();
    log(w, "sheet need preselected:", need);
    await page.waitForTimeout(300);
    await page.screenshot({ path: `${OUT}/sheet-${w}.png` });
    await page.close();
  }
}

async function pay() {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await ctx.newPage();
  await page.goto(`${WEB}/marketing/packages`, { waitUntil: "networkidle", timeout: 120000 });
  const sec = page.locator("#pay-as-you-go");
  await sec.scrollIntoViewIfNeeded();
  { const b = sec.getByRole("button", { name: "Buy now" }); await b.evaluate((e) => e.scrollIntoView({ block: "center" })); await b.click(); }
  const sheet = page.locator(".mk-buy");
  await sheet.waitFor();
  await sheet.locator("select").first().selectOption("physiotherapy");
  await sheet.getByLabel("Anything we should know?").fill("Knee exercises after surgery");
  const d = new Date(Date.now() + 2 * 86400000);
  await sheet.locator("input[type=date]").fill(d.toISOString().slice(0, 10));
  await sheet.getByLabel("Time of day").selectOption("morning");
  await sheet.getByLabel("Your name").fill("E2E Visit Test");
  await sheet.getByLabel("Mobile").fill("8309500488");
  await sheet.getByLabel("Email", { exact: false }).fill("e2e-visit@example.com");
  await sheet.getByLabel("City (optional)").fill("Hyderabad");
  await sheet.locator(".mk-buy-terms input").check();
  const verifyP = page.waitForResponse((r) => r.url().includes("/verify"), { timeout: 240000 });
  const startP = page.waitForResponse((r) => /plan-purchases$/.test(r.url()) && r.request().method() === "POST");
  await sheet.locator("button[type=submit]").click();
  const start = await (await startP).json();
  log("start:", start.reference, start.price?.amount_paise, start.payment?.provider, (start.payment?.order_id || "").slice(0, 6));

  const fr = page.frameLocator("iframe.razorpay-checkout-frame");
  const cards = fr.locator("[data-testid=Cards]");
  await cards.waitFor({ timeout: 60000 }).catch(async () => {
    await page.screenshot({ path: `${OUT}/rzp-debug1.png` });
    throw new Error("no Cards option");
  });
  await cards.click();
  await fr.locator("input[name='card.number']").pressSequentially("4100280000001007", { delay: 40 });
  await fr.locator("input[name='card.expiry']").pressSequentially("1226", { delay: 40 });
  await fr.locator("input[name='card.cvv']").pressSequentially("123", { delay: 40 });
  await page.screenshot({ path: `${OUT}/rzp-card.png` });
  const popupP = ctx.waitForEvent("page", { timeout: 60000 }).catch(() => null);
  const btn = fr.locator("button:visible", { hasText: /^(Pay|Continue|Pay Now|Pay ₹)/ }).last();
  await btn.click();
  log("clicked pay in frame");
  // Razorpay may ask to save the card / skip; click "Maybe later" / "Skip" if it shows.
  for (const t of ["Maybe later", "Skip saving card", "Skip"]) {
    const b = fr.getByText(t, { exact: false }).first();
    if (await b.isVisible().catch(() => false)) { await b.click().catch(() => {}); log("clicked", t); }
  }
  const popup = await popupP;
  if (popup) {
    await popup.waitForLoadState().catch(() => {});
    log("popup", popup.url().slice(0, 40));
    const ok = popup.getByRole("button", { name: /success/i }).or(popup.getByText(/^success$/i)).first();
    await ok.waitFor({ timeout: 60000 });
    await ok.click();
    log("clicked Success");
  } else {
    await page.screenshot({ path: `${OUT}/rzp-debug2.png` });
    log("no popup");
  }
  const v = await verifyP;
  log("verify:", v.status(), JSON.stringify(await v.json()));
  await sheet.getByText("Thank you — payment received.").waitFor({ timeout: 30000 });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/thanks-1440.png` });
  await ctx.close();
  return start.reference;
}

async function ops() {
  for (const w of [390, 768, 1440]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: w === 390 ? 844 : 1000 } });
    const page = await ctx.newPage();
    await page.goto(`${WEB}/login`, { waitUntil: "networkidle", timeout: 120000 });
    await page.locator("#email").fill("admin@sunrise-care.example");
    await page.locator("#password").fill("demo1234");
    await page.locator("button[type=submit]").first().click();
    await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 60000 });
    await page.goto(`${WEB}/kushalaya/visits?tab=requests`, { waitUntil: "networkidle", timeout: 120000 });
    const card = page.locator(".vs-req li", { has: page.locator(".vs-req-paid") }).first();
    await card.waitFor({ timeout: 30000 });
    log(w, "ops badge:", await card.locator(".vs-req-paid").innerText());
    await card.scrollIntoViewIfNeeded();
    await card.screenshot({ path: `${OUT}/ops-request-${w}.png` });
    await ctx.close();
  }
}

try {
  if (STEP === "all" || STEP === "shots") await sectionShots();
  if (STEP === "all" || STEP === "pay") await pay();
  if (STEP === "all" || STEP === "ops") await ops();
} finally {
  await browser.close();
}
