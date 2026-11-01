import { expect, test, type Page } from "@playwright/test";
import { DEMO_USERS, apiToken, loginAs } from "./helpers/auth";
import { API_URL } from "./helpers/hosts";

/**
 * Field checklist (app/caregiver/assess/[id]): submit is never a silent no-op —
 * unanswered questions are listed with a jump to the first one — on iPad and
 * phone sizes. Lead "Start assessment" + "Continue the draft" (assessment_start.py).
 */

const SIZES = [
  { name: "ipad-landscape", width: 1024, height: 768 },
  { name: "ipad-portrait", width: 768, height: 1024 },
  { name: "phone", width: 390, height: 844 },
];
const SHOTS = process.env.E2E_SHOTS_DIR;

async function api<T>(page: Page, token: string, path: string, data?: unknown): Promise<T> {
  const headers = { Authorization: `Bearer ${token}` };
  const res = data === undefined
    ? await page.request.get(`${API_URL}${path}`, { headers })
    : await page.request.post(`${API_URL}${path}`, { headers, data });
  expect(res.ok(), await res.text()).toBeTruthy();
  return (await res.json()) as T;
}

test.describe("Assessment checklist", () => {
  test.describe.configure({ timeout: 120_000 });

  for (const size of SIZES) {
    test(`submit shows what is unanswered (${size.name})`, async ({ page }) => {
      await page.setViewportSize({ width: size.width, height: size.height });
      const token = await apiToken(page, DEMO_USERS.tenantAdmin);
      const targets = await api<{ kind: string; elder_id: number | null }[]>(page, token, "/api/v1/jobs/assessment-targets");
      const client = targets.find((t) => t.kind === "client" && t.elder_id);
      expect(client).toBeTruthy();
      const started = await api<{ job_id: number }>(page, token, "/api/v1/jobs/start-assessment", {
        elder_id: client!.elder_id,
        new: true,
      });

      await loginAs(page, DEMO_USERS.tenantAdmin, `/caregiver/assess/${started.job_id}?from=assessments`);
      await page.getByRole("button", { name: /^(Start|Continue)$/ }).click();
      const sections = page.locator(".fa-sec");
      await sections.last().click();
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/section-${size.name}.png` });
      // No sideways scrolling at this size.
      const [sw, iw] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
      expect(sw).toBeLessThanOrEqual(iw);
      await page.getByRole("button", { name: "Review" }).click();

      const left = page.locator(".fa-left");
      await expect(left).toContainText("not answered yet");
      await page.getByRole("button", { name: "Submit assessment" }).click();
      await expect(page.locator(".fa-left.is-alert")).toBeVisible();
      await expect(page.locator(".fa-left.is-alert")).toBeInViewport();
      if (SHOTS) await page.screenshot({ path: `${SHOTS}/blocked-${size.name}.png` });

      await page.getByRole("button", { name: "Go to the first unanswered question" }).click();
      const first = page.locator(".fa-item.is-missing").first();
      await expect(first).toBeInViewport();
      await expect(first.locator(".fa-tag")).toHaveText("Not answered yet");
      // The sticky bars stay visible while scrolled.
      await expect(page.locator(".fa-sections")).toBeInViewport();

      // Answer one, then Save draft works with most questions still open.
      await first.locator(".fa-opt").last().click();
      await page.getByRole("button", { name: "Save draft" }).click();
      await expect(page.locator(".fa-bar-text small")).toContainText("Saved");
    });
  }

  test("lead: Start assessment, then Continue the draft", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    const token = await apiToken(page, DEMO_USERS.tenantAdmin);
    const name = `E2E Lead ${Date.now()}`;
    const lead = await api<{ id: number }>(page, token, "/api/v1/sales/leads", {
      name,
      source: "Phone call",
      phone: "9876500099",
    });

    // Local demo data may hold an open SOS; its notice would cover the page.
    await page.addInitScript(() => {
      document.addEventListener("DOMContentLoaded", () => {
        const css = document.createElement("style");
        css.textContent = ".ks-siren { display: none !important; }";
        document.head.appendChild(css);
      });
    });
    await loginAs(page, DEMO_USERS.tenantAdmin, "/kushalaya/enquiries");
    await page.getByRole("button", { name }).first().click();
    await page.getByRole("dialog", { name }).getByRole("button", { name: "Start assessment" }).click();
    await expect(page).toHaveURL(/\/caregiver\/assess\/\d+\?from=leads/);
    await expect(page.locator(".fa-bar-text strong")).toContainText("E2E Lead");

    // "New assessment" lists the lead, with its open draft.
    await page.goto("/kushalaya/assessments");
    await page.getByRole("button", { name: "+ New assessment" }).click();
    const picker = page.getByLabel("Client or lead");
    await expect(picker.locator("option", { hasText: name })).toHaveText(`${name} · lead · draft open`);
    await picker.selectOption({ label: `${name} · lead · draft open` });
    await page.getByRole("button", { name: "Start the checklist" }).click();
    await expect(page.getByRole("button", { name: "Continue the draft" })).toBeFocused();

    const leads = await api<{ id: number; stage: string }[]>(page, token, "/api/v1/sales/leads");
    expect(leads.find((l) => l.id === lead.id)?.stage).toBe("ASSESSMENT_SCHEDULED");
  });
});
