/**
 * Dump LiveWell360 FE library defaults into backend JSON seeds.
 *
 * Usage (from frontend/):
 *   npx --yes tsx scripts/dump-livewell-defaults.ts
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { DEFAULT_SAFETY_CATALOG } from "../lib/livewell/catalog-defaults";
import { LWA_CATEGORIES, LWA_TITLE, LWA_VERSION } from "../lib/livewell/lwa-rubric";
import { DEFAULT_SOLUTION_LIBRARY } from "../lib/livewell/solution-defaults";

const here = path.dirname(fileURLToPath(import.meta.url));
const backendHomeSafety = path.resolve(here, "../../backend/app/livewell");

function writeJson(filename: string, data: unknown) {
  const out = path.join(backendHomeSafety, filename);
  fs.writeFileSync(out, `${JSON.stringify(data, null, 2)}\n`, "utf8");
  console.log(`Wrote ${out}`);
}

const solutionsPayload = {
  solutions: DEFAULT_SOLUTION_LIBRARY.solutions.map((s) => ({
    ...s,
    maintenanceRequirement: s.maintenanceRequirement ?? "",
    futureUpgrades: s.futureUpgrades ?? "",
  })),
};

const rubricPayload = {
  title: LWA_TITLE,
  version: LWA_VERSION,
  source: "livewell360",
  categories: LWA_CATEGORIES,
};

writeJson("default_solutions.json", solutionsPayload);
writeJson("default_rubric.json", rubricPayload);
writeJson("default_catalog.json", DEFAULT_SAFETY_CATALOG);

const prefixCounts: Record<string, number> = {};
for (const s of DEFAULT_SOLUTION_LIBRARY.solutions) {
  const prefix = s.id.replace(/-\d+$/, "");
  prefixCounts[prefix] = (prefixCounts[prefix] ?? 0) + 1;
}
console.log("Solution counts by prefix:", prefixCounts);
console.log(
  `Products: ${DEFAULT_SAFETY_CATALOG.products.length}, packages: ${DEFAULT_SAFETY_CATALOG.packages.length}`,
);
