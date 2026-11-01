import type { SolutionLibrary } from "./solution-types";
import raw from "./default_solutions.json";

/** Canonical Library v1 defaults (synced from backend/app/livewell/default_solutions.json). */
export const DEFAULT_SOLUTION_LIBRARY = raw as SolutionLibrary;

/** Stable rubric item id from category key + human label (admin linking helper). */
export function rubricItemId(categoryId: string, label: string): string {
  const cat = categoryId.trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  const item = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");
  return `${cat}_${item}`;
}
