import { test, expect } from "@playwright/test";
import { loginAsTenantAdmin } from "./helpers/auth";
import { API_URL } from "./helpers/hosts";

test.describe("Assessment questions", () => {
  test.describe.configure({ timeout: 120_000 });
  test("admin question edits show on the next assessment, not in the live wizard", async ({
    page,
  }) => {
    await loginAsTenantAdmin(page);
    const auth = await page.evaluate(() =>
      JSON.parse(window.localStorage.getItem("sho_auth") || "{}"),
    );
    const headers = { Authorization: `Bearer ${auth.access_token}` };
    const originalRes = await page.request.get(`${API_URL}/api/v1/home-safety/rubric`, {
      headers,
    });
    expect(originalRes.ok()).toBeTruthy();
    const original = await originalRes.json();
    const label = `E2E custom ${Date.now()}`;

    try {
      await page.goto("/kushalaya/rubric");
      await expect(page.getByRole("heading", { name: "Assessment questions" })).toBeVisible();
      const firstStage = page.locator(".home-safety-rubric-admin section.card").first();
      // Sections start collapsed.
      await firstStage.getByRole("button", { name: /^Open/ }).click();
      await firstStage.getByRole("button", { name: "+ Add question" }).click();
      const newRow = firstStage.locator("tbody tr").last();
      await newRow.getByLabel("Question", { exact: true }).fill(label);
      await newRow.getByLabel("Question type").selectOption("yesno");
      await page.getByRole("button", { name: "Save questions" }).click();
      await expect(page.getByText(/Saved\. Caregivers get these questions/i)).toBeVisible({ timeout: 20_000 });

      const saved = await page.request.get(`${API_URL}/api/v1/home-safety/rubric`, { headers });
      const savedBody = await saved.json();
      const labels = (savedBody.categories ?? []).flatMap((c: { items?: { label?: string; inputType?: string }[] }) =>
        c.items ?? [],
      );
      expect(labels.some((i: { label?: string }) => i.label === label)).toBeTruthy();
      expect(labels.find((i: { label?: string }) => i.label === label)?.inputType).toBe("yesno");

      await page.goto("/kushalaya/assessments");
      await page.getByRole("button", { name: "+ New assessment" }).click();
      await expect(page.getByLabel(/First name/i)).toBeVisible({ timeout: 20_000 });
      await expect(page.getByRole("button", { name: "Edit questions" })).toHaveCount(0);
      await expect(page.getByRole("button", { name: "Next" })).toBeVisible();
      await page.getByLabel(/First name/i).fill("E2E");
      await page.getByRole("button", { name: "Next" }).click();

      let found = false;
      for (let i = 0; i < 20; i++) {
        if (await page.getByText(label).isVisible().catch(() => false)) {
          found = true;
          break;
        }
        const next = page.getByRole("button", { name: "Next" });
        if (await next.isDisabled()) break;
        await next.click();
      }
      expect(found, "saved question should appear on an assessment stage").toBeTruthy();
      await expect(page.getByRole("button", { name: "Yes" }).first()).toBeVisible();
      await expect(page.getByRole("button", { name: "Edit questions" })).toHaveCount(0);

      const body = page.locator(".home-safety-wizard-body");
      await body.evaluate((el) => {
        el.scrollTop = el.scrollHeight;
      });
      await expect(page.getByRole("button", { name: "Next" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Back" })).toBeVisible();
    } finally {
      await page.request.put(`${API_URL}/api/v1/home-safety/rubric`, {
        headers,
        data: original,
      });
    }
  });
});
