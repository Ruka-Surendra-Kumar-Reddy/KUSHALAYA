/**
 * Dump LiveWell360 FE defaults → backend/app/livewell/*.json
 *
 * Usage (from frontend/):
 *   node scripts/dump-livewell-defaults.mjs
 *   # or:
 *   npx vite-node scripts/dump-livewell-defaults.ts
 */
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.join(here, "..");
const entry = path.join(here, "dump-livewell-defaults.ts");
const viteNode = path.join(
  frontendRoot,
  "node_modules",
  ".bin",
  process.platform === "win32" ? "vite-node.cmd" : "vite-node",
);

const result = spawnSync(viteNode, [entry], {
  stdio: "inherit",
  cwd: frontendRoot,
  shell: process.platform === "win32",
});
process.exit(result.status ?? 1);
