// Copies Capacitor's config/plugins into the Android project, then writes one
// capacitor.config.json per app (flavor) so each loads its own site:
//   ops    -> https://ops.kushalaya.com     (staff + caregivers at /caregiver)
//   family -> https://family.kushalaya.com
import { execSync } from "node:child_process";
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
export const APPS = {
  ops: { appId: "com.kushalaya.ops", appName: "KushAlaya Ops", url: "https://ops.kushalaya.com" },
  family: { appId: "com.kushalaya.family", appName: "KushAlaya Family", url: "https://family.kushalaya.com" },
};

execSync("npx cap sync android", { cwd: root, stdio: "inherit" });

const mainCfg = join(root, "android/app/src/main/assets/capacitor.config.json");
const base = JSON.parse(readFileSync(mainCfg, "utf8"));
for (const [flavor, app] of Object.entries(APPS)) {
  const cfg = { ...base, appId: app.appId, appName: app.appName, server: { ...base.server, url: app.url } };
  const out = join(root, `android/app/src/${flavor}/assets/capacitor.config.json`);
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, JSON.stringify(cfg, null, 2) + "\n");
  console.log(`${flavor}: ${app.url}`);
}
// Only the per-flavor copies may exist, so neither app can load the other's site.
rmSync(mainCfg, { force: true });
