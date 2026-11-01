import { test } from "@playwright/test";

// ElderCare workforce academy surfaces are not shipped in SafeHomeOps.
test.describe.skip("Workforce Academy (ElderCare-only)", () => {
  test("placeholder", async () => {});
});
