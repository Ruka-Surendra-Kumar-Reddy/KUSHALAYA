/**
 * Generate docs/livewell/ASSESSOR_ITEM_TRAINING.md from assessor-item-training.ts
 * Usage (from frontend/): npx tsx scripts/generate-assessor-training-md.ts
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { ASSESSOR_ITEM_TRAINING } from "../lib/livewell/assessor-item-training";
import { LWA_CATEGORIES, LWA_TITLE, LWA_VERSION } from "../lib/livewell/lwa-rubric";

const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.resolve(here, "../../docs/livewell/ASSESSOR_ITEM_TRAINING.md");

const lines: string[] = [
  "# Assessor item training — LiveWell360 Assessment (KAA)",
  "",
  `**${LWA_TITLE}** · checklist v${LWA_VERSION} · ${ASSESSOR_ITEM_TRAINING.length} items`,
  "",
  "Field guide for assessors: what to look for on each checklist item, and how to choose **Excellent**, **Acceptable**, **Unsafe**, or **N/A**.",
  "",
  "In the app: open **Scoring & training** (`/kushalaya/scoring`), or tap **?** next to any question during an assessment.",
  "",
  "## Rating scale (quick reference)",
  "",
  "| Rating | Meaning |",
  "|--------|---------|",
  "| ★ Excellent | Fully safe / compliant for this home and elder |",
  "| ~ Acceptable | Partial support or minor gap — note it |",
  "| ✕ Unsafe | Immediate risk or missing critical support |",
  "| — N/A | Not applicable — excluded from score |",
  "",
  "Be dignity-first: describe risk and support needs, never shame the elder.",
  "",
];

for (const cat of LWA_CATEGORIES) {
  const items = ASSESSOR_ITEM_TRAINING.filter((t) => t.categoryId === cat.id);
  if (!items.length) continue;
  const bare = cat.title.replace(/^\d+\.\s*/, "");
  const title = cat.sectionNumber ? `${cat.sectionNumber}. ${bare}` : cat.title;
  lines.push(`## ${title}`, "");
  for (const t of items) {
    lines.push(`### ${t.label}`, "");
    lines.push(`**Look for:** ${t.lookFor}`, "");
    lines.push(`- **Excellent:** ${t.excellent}`);
    lines.push(`- **Acceptable:** ${t.acceptable}`);
    lines.push(`- **Unsafe:** ${t.unsafe}`);
    lines.push(`- **N/A when:** ${t.naWhen}`);
    if (t.tip) lines.push(`- **Tip:** ${t.tip}`);
    lines.push("");
  }
}

fs.writeFileSync(out, `${lines.join("\n")}\n`, "utf8");
console.log(`Wrote ${out} (${ASSESSOR_ITEM_TRAINING.length} items)`);
