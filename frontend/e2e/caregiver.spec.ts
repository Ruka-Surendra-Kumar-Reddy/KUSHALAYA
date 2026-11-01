import { test, expect } from "@playwright/test";
import { DEMO_USERS, apiToken, uiLoginOps } from "./helpers/auth";
import { API_URL } from "./helpers/hosts";

const HYDERABAD = { latitude: 17.385, longitude: 78.4867 };

// Caregiver field app (/caregiver) on the ops host, location mocked.
// Check-in rules are being changed elsewhere, so this only checks that the
// day view loads and offers "Check in" for a visit booked today.
test.describe("Caregiver app", () => {
  test("caregiver signs in and sees today's visits with a check-in button", async ({ page, context }) => {
    await context.grantPermissions(["geolocation"]);
    await context.setGeolocation(HYDERABAD);

    // The seed has no visit for today, so book one for Anita (caregiver 1,
    // client 1) and cancel it afterwards.
    const token = await apiToken(page, DEMO_USERS.careManager);
    const headers = { Authorization: `Bearer ${token}` };
    const istDate = (d: Date) => new Date(d.getTime() + 5.5 * 3600 * 1000).toISOString().slice(0, 10);
    let when = new Date(Date.now() + 60 * 60 * 1000);
    if (istDate(when) !== istDate(new Date())) when = new Date(Date.now() + 60 * 1000);
    const title = `E2E visit ${Date.now()}`;
    const created = await page.request.post(`${API_URL}/api/v1/jobs`, {
      headers,
      data: {
        elder_id: 1,
        caregiver_id: 1,
        kind: "visit",
        title,
        scheduled_at: when.toISOString(),
        duration_minutes: 30,
        force: true,
      },
    });
    expect(created.ok(), await created.text()).toBeTruthy();
    const job = await created.json();

    try {
      await uiLoginOps(page, DEMO_USERS.caregiver);
      await expect(page).toHaveURL(/\/caregiver$/, { timeout: 60_000 });
      await expect(page.getByRole("heading", { level: 1 })).toContainText(/Anita/);
      await expect(page.getByRole("heading", { name: "Today", exact: true })).toBeVisible();
      const card = page.locator("li.cg-visit").filter({ hasText: title });
      await expect(card).toBeVisible();
      await expect(card.getByRole("button", { name: "Check in" })).toBeVisible();
    } finally {
      const done = await page.request.patch(`${API_URL}/api/v1/jobs/${job.id}`, {
        headers,
        data: { status: "cancelled" },
      });
      expect(done.ok(), `clean-up of job ${job.id}: ${await done.text()}`).toBeTruthy();
    }
  });
});
