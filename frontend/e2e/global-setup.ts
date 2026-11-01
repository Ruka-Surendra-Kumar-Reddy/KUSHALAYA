import { execSync } from "child_process";
import fs from "fs";
import path from "path";

const apiURL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8010";
const backendDir = path.join(__dirname, "..", "..", "backend");
const frontendDir = path.join(__dirname, "..");

/** Project venv python (has workforceos_core); plain `python` as a fallback. */
export function backendPython(): string {
  const candidates = [
    path.join(backendDir, ".venv", "Scripts", "python.exe"),
    path.join(backendDir, ".venv", "bin", "python"),
  ];
  const found = candidates.find((p) => fs.existsSync(p));
  return found ? `"${found}"` : "python";
}

/** Ensure Next.js dev server sees the API URL at startup. */
function writeEnvLocal() {
  const envPath = path.join(frontendDir, ".env.local");
  fs.writeFileSync(
    envPath,
    `NEXT_PUBLIC_API_URL=${apiURL}\n`,
    "utf8",
  );
}

async function waitForHealth(maxMs = 90_000) {
  const start = Date.now();
  while (Date.now() - start < maxMs) {
    try {
      const res = await fetch(`${apiURL}/health`);
      if (res.ok) return;
    } catch {
      /* retry */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`API not ready at ${apiURL}/health`);
}

const DEMO_ACCOUNTS = [
  { email: "manager@sunrise-care.example", password: "demo1234" },
  { email: "admin@sunrise-care.example", password: "demo1234" },
  { email: "anita.caregiver@sunrise-care.example", password: "demo1234" },
  { email: "lakshmi.family@sunrise-care.example", password: "demo1234" },
];

async function allDemoLoginsWork(): Promise<boolean> {
  try {
    for (const account of DEMO_ACCOUNTS) {
      const res = await fetch(`${apiURL}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(account),
      });
      if (!res.ok) return false;
    }
    return true;
  } catch {
    return false;
  }
}

export default async function globalSetup() {
  if (process.env.PLAYWRIGHT_SKIP_SETUP) return;

  writeEnvLocal();
  await waitForHealth();

  if (await allDemoLoginsWork()) return;

  const py = backendPython();
  const steps = [
    `${py} -m app.init_db`,
    `${py} -m app.db_migrate`,
    `${py} -m app.seed_care_demo`,
  ];

  for (const cmd of steps) {
    execSync(cmd, { cwd: backendDir, stdio: "inherit", env: process.env });
  }

  if (!(await allDemoLoginsWork())) {
    throw new Error(
      "E2E setup failed: demo login unavailable. Run backend seed manually.",
    );
  }
}
