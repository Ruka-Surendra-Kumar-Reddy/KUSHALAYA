import type { AssessmentCategory } from "./assessment";
import { DEFAULT_SAFETY_CATEGORIES } from "./rubric-defaults";
import { helpForRubricItem } from "./rubric-item-help";
import { readLocalStorageWithLegacy, removeLocalStorageKeys } from "./legacyStorage";

const RUBRIC_STORAGE_KEY = "safehome_home_safety_rubric_v2";
const LEGACY_RUBRIC_KEYS = ["eldercare_home_safety_rubric_v2"];

function syncCategoryMaxPoints(categories: AssessmentCategory[]): AssessmentCategory[] {
  return categories.map((cat) => ({
    ...cat,
    maxPoints: cat.items.reduce((s, i) => s + i.maxPoints, 0),
  }));
}

export function normalizeRubric(categories: AssessmentCategory[]): AssessmentCategory[] {
  return syncCategoryMaxPoints(
    categories.map((cat) => ({
      ...cat,
      items: cat.items.map((item) => ({
        ...item,
        maxPoints: Math.max(1, Math.round(item.maxPoints)),
      })),
    })),
  );
}

/** Backfill `source` and assessor `help` from factory defaults / help map. */
function mergeGuidanceFromDefaults(categories: AssessmentCategory[]): AssessmentCategory[] {
  const defaultById = new Map(
    DEFAULT_SAFETY_CATEGORIES.flatMap((cat) => cat.items.map((item) => [item.id, item] as const)),
  );
  return categories.map((cat) => ({
    ...cat,
    items: cat.items.map((item) => {
      const fromDefault = defaultById.get(item.id);
      return {
        ...item,
        source: item.source ?? fromDefault?.source ?? "safehome360",
        help: helpForRubricItem({
          id: item.id,
          label: item.label,
          help: item.help ?? fromDefault?.help,
        }),
      };
    }),
  }));
}

export function normalizeRubricWithSources(categories: AssessmentCategory[]): AssessmentCategory[] {
  return mergeGuidanceFromDefaults(normalizeRubric(categories));
}

export function rubricTotalMax(categories: AssessmentCategory[]): number {
  return categories.reduce((s, c) => s + c.maxPoints, 0);
}

export function getCachedRubric(): AssessmentCategory[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = readLocalStorageWithLegacy(RUBRIC_STORAGE_KEY, LEGACY_RUBRIC_KEYS);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as AssessmentCategory[];
    if (!Array.isArray(parsed) || parsed.length === 0) return [];
    return normalizeRubricWithSources(parsed);
  } catch {
    return [];
  }
}

export function getSafetyCategories(): AssessmentCategory[] {
  const cached = getCachedRubric();
  if (cached.length) return cached;
  return normalizeRubricWithSources(DEFAULT_SAFETY_CATEGORIES);
}

export function saveSafetyCategories(categories: AssessmentCategory[]): AssessmentCategory[] {
  const normalized = normalizeRubricWithSources(categories);
  localStorage.setItem(RUBRIC_STORAGE_KEY, JSON.stringify(normalized));
  removeLocalStorageKeys(...LEGACY_RUBRIC_KEYS);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("home-safety-rubric-updated"));
  }
  return normalized;
}

export function resetSafetyCategories(): AssessmentCategory[] {
  removeLocalStorageKeys(RUBRIC_STORAGE_KEY, ...LEGACY_RUBRIC_KEYS);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("home-safety-rubric-updated"));
  }
  return normalizeRubricWithSources(DEFAULT_SAFETY_CATEGORIES);
}

export function newCategoryId(title: string): string {
  const base = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "")
    .slice(0, 24);
  return `${base || "category"}_${Date.now().toString(36)}`;
}

export function newItemId(categoryId: string, label: string): string {
  const base = label
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "")
    .slice(0, 20);
  return `${categoryId}_${base || "item"}_${Math.random().toString(36).slice(2, 7)}`;
}
