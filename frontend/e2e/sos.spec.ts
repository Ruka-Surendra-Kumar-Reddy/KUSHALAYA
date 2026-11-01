import { expect, test, type Browser, type Page } from "@playwright/test";
import { DEMO_PASSWORD, DEMO_USERS } from "./helpers/auth";

/**
 * SOS end to end (owner, 27 Oct): whoever raises it — family, Ops or a
 * caregiver — the linked people see the siren notice and hear the hooter.
 * The hooter is Web Audio, so we count oscillator starts instead of listening.
 * Runs against local servers only (the siren polls every ~12 s).
 */
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8010";
const ELDER_ID = 1; // Lakshmi Reddy in the demo seed
const SIREN_WAIT = 45_000;

const AUDIO_PROBE = () => {
  (window as unknown as { __sirenStarts: number }).__sirenStarts = 0;
  // The siren is a recorded file (AudioBufferSourceNode); the backup is generated (OscillatorNode).
  type Startable = { prototype: { start: (...a: unknown[]) => void } };
  const w = window as unknown as { OscillatorNode?: Startable; AudioBufferSourceNode?: Startable };
  for (const node of [w.OscillatorNode, w.AudioBufferSourceNode]) {
    if (!node) continue;
    const start = node.prototype.start;
    node.prototype.start = function (this: unknown, ...a: unknown[]) {
      (window as unknown as { __sirenStarts: number }).__sirenStarts += 1;
      return start.apply(this, a);
    };
  }
};

async function opened(browser: Browser): Promise<Page> {
  const ctx = await browser.newContext();
  await ctx.addInitScript(AUDIO_PROBE);
  return ctx.newPage();
}

async function opsLogin(page: Page, email: string) {
  await page.goto("/login");
  await page.fill("#email", email);
  await page.fill("#password", DEMO_PASSWORD);
  await page.click("button[type=submit]");
  await page.waitForURL(/dashboard|caregiver/, { timeout: 90_000 });
}

/** Lakshmi's own login ("self") and her son Arjun's family login. The siren rings
 *  for family members; the parent's own phone is not sounded for her own emergency. */
const LAKSHMI_SELF = DEMO_USERS.elderPortal.email;
const ARJUN_FAMILY = "arjun.family@sunrise-care.example";

async function familyLogin(page: Page, email: string = LAKSHMI_SELF) {
  await page.goto("/kushalaya/family/login");
  await page.fill("input[type=email]", email);
  await page.fill("input[type=password]", DEMO_PASSWORD);
  await page.click("button[type=submit]");
  await page.waitForURL((u) => !/login/.test(String(u)), { timeout: 90_000 });
  // First visit asks for privacy choices; accept the required one if shown.
  const gate = page.getByRole("dialog", { name: /privacy/i });
  if (await gate.isVisible().catch(() => false)) {
    await gate.getByRole("checkbox").last().check().catch(() => undefined);
    await gate.getByRole("button", { name: /continue|agree|save/i }).first().click().catch(() => undefined);
  }
}

/** Browsers only play sound after a user gesture: click once, like a real user. */
async function unlockAudio(page: Page) {
  await page.mouse.click(5, 5);
}

async function expectSirenHeard(page: Page) {
  await expect(page.locator(".ks-siren")).toBeVisible({ timeout: SIREN_WAIT });
  await expect
    .poll(() => page.evaluate(() => (window as unknown as { __sirenStarts: number }).__sirenStarts), { timeout: 15_000 })
    .toBeGreaterThan(0);
}

async function token(page: Page, email: string): Promise<string> {
  const res = await page.request.post(`${API_URL}/api/v1/auth/login`, { data: { email, password: DEMO_PASSWORD } });
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()).access_token;
}

/** Leave no open SOS behind for the next test. */
async function acknowledgeAll(page: Page) {
  for (let i = 0; i < 6; i++) {
    const ack = page.locator(".ks-siren").getByRole("button", { name: "Acknowledge" }).first();
    if (!(await ack.isVisible().catch(() => false))) return;
    await ack.click();
    await page.waitForTimeout(800);
  }
}

/**
 * A second SOS for a client with one already open joins it (no new alarm), so
 * each test starts by closing the client's open emergencies.
 */
async function closeOpenSos(request: import("@playwright/test").APIRequestContext) {
  const login = await request.post(`${API_URL}/api/v1/auth/login`, {
    data: { email: DEMO_USERS.tenantAdmin.email, password: DEMO_PASSWORD },
  });
  const headers = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const rows = (await (await request.get(`${API_URL}/api/v1/care/incidents`, { headers })).json()) as {
    id: number;
    elder_id: number | null;
  }[];
  for (const r of rows.filter((x) => x.elder_id === ELDER_ID)) {
    // Staff-raised emergencies close through their own step; other SOS resolve.
    const close = await request.post(`${API_URL}/api/v1/care/incidents/${r.id}/emergency/close`, {
      headers,
      data: { outcome: "resolved_home", note: "E2E clean-up" },
    });
    if (!close.ok()) {
      await request.post(`${API_URL}/api/v1/care/incidents/${r.id}/resolve`, {
        headers,
        data: { outcome: "contacted_family", note: "E2E clean-up" },
      });
    }
  }
}

test.describe("SOS siren", () => {
  test.setTimeout(240_000);
  test.beforeEach(async ({ request }) => {
    await closeOpenSos(request);
  });

  test("family presses SOS → the manager sees the notice and hears the hooter", async ({ browser }) => {
    const ops = await opened(browser);
    await opsLogin(ops, DEMO_USERS.tenantAdmin.email);
    await unlockAudio(ops);
    await acknowledgeAll(ops);

    const family = await opened(browser);
    await familyLogin(family);
    await family.goto("/kushalaya/family/alerts");
    await family.getByRole("button", { name: "Send SOS" }).click();
    await family.getByRole("button", { name: "Yes, send SOS" }).click();
    await expect(family.getByText("SOS sent. Your care team has been alerted.")).toBeVisible({ timeout: 30_000 });

    await expectSirenHeard(ops);
    await expect(ops.locator(".ks-siren")).toContainText(/Lakshmi/);
    await acknowledgeAll(ops);
  });

  test("Ops raises SOS on a client → the family sees the notice and hears the hooter", async ({ browser }) => {
    const family = await opened(browser);
    await familyLogin(family, ARJUN_FAMILY);
    await unlockAudio(family);
    await acknowledgeAll(family);

    const ops = await opened(browser);
    await opsLogin(ops, DEMO_USERS.tenantAdmin.email);
    await ops.goto(`/kushalaya/customers/${ELDER_ID}`);
    await ops.getByRole("button", { name: /SOS — raise emergency/ }).click();
    const form = ops.getByRole("dialog");
    await form.locator("fieldset button").first().click(); // step 2: what happened
    await form.getByRole("button", { name: "Next" }).click();
    await form.getByRole("button", { name: "Confirm — raise emergency" }).click(); // step 3

    await expectSirenHeard(family);
    await acknowledgeAll(family);
    await unlockAudio(ops);
    await acknowledgeAll(ops);
  });

  test("a caregiver raises an emergency → the manager is alerted", async ({ browser }) => {
    const ops = await opened(browser);
    await opsLogin(ops, DEMO_USERS.tenantAdmin.email);
    await unlockAudio(ops);
    await acknowledgeAll(ops);

    const cg = await token(ops, DEMO_USERS.caregiver.email);
    const headers = { Authorization: `Bearer ${cg}` };
    const opts = await (await ops.request.get(`${API_URL}/api/v1/caregiver-portal/emergency/options`, { headers })).json();
    const res = await ops.request.post(`${API_URL}/api/v1/caregiver-portal/emergency`, {
      headers,
      data: { elder_id: ELDER_ID, type: opts.types[0].value, reported_by: opts.reporters?.[0]?.value, note: "E2E caregiver SOS" },
    });
    expect(res.ok(), await res.text()).toBeTruthy();

    await expectSirenHeard(ops);
    await acknowledgeAll(ops);
  });

  for (const [label, viewport] of [
    ["laptop", { width: 1280, height: 720 }],
    ["phone", { width: 390, height: 844 }],
  ] as const) {
    test(`anyone in Ops raises SOS from the top bar in 3 steps (${label})`, async ({ browser }) => {
      const family = await opened(browser);
      await familyLogin(family, ARJUN_FAMILY);
      await unlockAudio(family);
      await acknowledgeAll(family);

      const ctx = await browser.newContext({ viewport, isMobile: label === "phone", hasTouch: label === "phone" });
      await ctx.addInitScript(AUDIO_PROBE);
      const ops = await ctx.newPage();
      await opsLogin(ops, DEMO_USERS.careManager.email);
      await unlockAudio(ops);
      await acknowledgeAll(ops); // earlier alerts this manager already handled
      await ops.locator(".ko-topbar-right").getByRole("button", { name: "SOS", exact: true }).click();
      const form = ops.getByRole("dialog");
      // Step 1: find the client.
      await form.getByPlaceholder("Name, phone or customer ID").fill("Lakshmi");
      await form.getByRole("option", { name: /Lakshmi/ }).first().click();
      // Step 2: what happened.
      await form.locator("fieldset button").first().click();
      await form.getByRole("button", { name: "Next" }).click();
      // Step 3: check and confirm.
      await expect(form.locator(".ks-emg-summary")).toContainText("Lakshmi");
      await form.getByRole("button", { name: "Confirm — raise emergency" }).click();
      await ops.waitForURL(/kushalaya\/alerts/, { timeout: 30_000 });

      await expectSirenHeard(family);
      await acknowledgeAll(family);
      await ctx.close();
    });
  }

  test("same account on two devices: the other device rings, the pressing one stays quiet", async ({ browser }) => {
    const other = await opened(browser);
    await familyLogin(other, ARJUN_FAMILY);
    await unlockAudio(other);
    await acknowledgeAll(other);

    const presser = await opened(browser);
    await familyLogin(presser, ARJUN_FAMILY);
    await unlockAudio(presser);
    await presser.goto("/kushalaya/family/alerts");
    await presser.getByRole("button", { name: "Send SOS" }).click();
    await presser.getByRole("button", { name: "Yes, send SOS" }).click();
    await expect(presser.getByText("SOS sent. Your care team has been alerted.")).toBeVisible({ timeout: 30_000 });

    await expectSirenHeard(other); // the same account's other device rings
    await expect(presser.locator(".ks-siren")).toBeVisible({ timeout: SIREN_WAIT }); // notice still shows
    expect(await presser.evaluate(() => (window as unknown as { __sirenStarts: number }).__sirenStarts)).toBe(0);
    await acknowledgeAll(other);
  });
});
