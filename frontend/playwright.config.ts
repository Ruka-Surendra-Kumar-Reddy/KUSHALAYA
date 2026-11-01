import { defineConfig, devices } from "@playwright/test";
import fs from "fs";
import path from "path";

const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3010";
const apiURL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8010";
const backendDir = path.join(__dirname, "..", "backend");
// Project venv python: plain `python` on this machine lacks workforceos_core.
const venvPython = [
  path.join(backendDir, ".venv", "Scripts", "python.exe"),
  path.join(backendDir, ".venv", "bin", "python"),
].find((p) => fs.existsSync(p));
const python = venvPython ? `"${venvPython}"` : "python";
const reuseBackend =
  !!process.env.PLAYWRIGHT_REUSE_SERVERS || !process.env.CI;
const reuseFrontend = !!process.env.PLAYWRIGHT_REUSE_SERVERS;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  globalSetup: require.resolve("./e2e/global-setup.ts"),
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: process.env.PLAYWRIGHT_SKIP_SERVERS
    ? undefined
    : [
        {
          command:
            `${python} -m uvicorn app.main:app --host 127.0.0.1 --port 8010`,
          cwd: backendDir,
          url: `${apiURL}/health`,
          reuseExistingServer: reuseBackend,
          timeout: 120_000,
          env: {
            SECRET_KEY: "e2e-test-secret",
            ENABLE_TELEMETRY: "false",
            ENVIRONMENT: "test",
          },
        },
        {
          command: "npm run dev -- -p 3010",
          url: baseURL,
          reuseExistingServer: reuseFrontend,
          timeout: 120_000,
          env: {
            NEXT_PUBLIC_API_URL: apiURL,
          },
        },
      ],
});
