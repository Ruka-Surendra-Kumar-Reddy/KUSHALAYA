import type { SafeHomeSolution, SolutionLibrary } from "./solution-types";
import { DEFAULT_SOLUTION_LIBRARY } from "./solution-defaults";
import { readLocalStorageWithLegacy, removeLocalStorageKeys } from "./legacyStorage";

const STORAGE_KEY = "safehome_home_safety_solutions_v1";
const LEGACY_STORAGE_KEYS = ["eldercare_home_safety_solutions_v1"];

export type { SafeHomeSolution, SolutionLibrary, SolutionPriority } from "./solution-types";
export { DEFAULT_SOLUTION_LIBRARY, rubricItemId } from "./solution-defaults";
export {
  SOLUTION_PRIORITY_META,
  SOLUTION_PRIORITY_ORDER,
} from "./solution-types";

export function normalizeSolutionLibrary(raw: SolutionLibrary): SolutionLibrary {
  const solutions = (raw.solutions ?? [])
    .filter((s) => s.id && (s.finding?.trim() || s.name?.trim()))
    .map((s, i) => ({
      ...s,
      name: (s.name ?? "").trim() || undefined,
      finding: (s.finding ?? s.name ?? "").trim(),
      riskDescription: (s.riskDescription ?? "").trim(),
      contractorType: (s.contractorType ?? "").trim(),
      estimatedCost: (s.estimatedCost ?? "").trim(),
      installationTime: (s.installationTime ?? "").trim(),
      maintenanceRequirement: (s.maintenanceRequirement ?? "").trim(),
      futureUpgrades: (s.futureUpgrades ?? "").trim(),
      recommendedSolutions: (s.recommendedSolutions ?? []).map((x) => x.trim()).filter(Boolean),
      productCategories: (s.productCategories ?? []).map((x) => x.trim()).filter(Boolean),
      rubricItemIds: [...new Set((s.rubricItemIds ?? []).filter(Boolean))],
      legacyIds: [...new Set((s.legacyIds ?? []).filter(Boolean))],
      scoreImprovement: Math.max(0, Number(s.scoreImprovement) || 0),
      sort_order: s.sort_order ?? i,
    }))
    .sort((a, b) => a.sort_order - b.sort_order);
  return {
    solutions,
    schemaVersion: raw.schemaVersion,
    libraryVersion: raw.libraryVersion,
  };
}

export function trimSolutionLibraryForSave(library: SolutionLibrary): SolutionLibrary {
  return normalizeSolutionLibrary(library);
}

export function getLocalSolutionLibrary(): SolutionLibrary {
  if (typeof window === "undefined") return { solutions: [] };
  try {
    const raw = readLocalStorageWithLegacy(STORAGE_KEY, LEGACY_STORAGE_KEYS);
    if (!raw) return { solutions: [] };
    return normalizeSolutionLibrary(JSON.parse(raw) as SolutionLibrary);
  } catch {
    return { solutions: [] };
  }
}

export function saveLocalSolutionLibrary(library: SolutionLibrary): SolutionLibrary {
  const normalized = normalizeSolutionLibrary(library);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
  removeLocalStorageKeys(...LEGACY_STORAGE_KEYS);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("home-safety-solutions-updated"));
  }
  return normalized;
}

export function resetLocalSolutionLibrary(): SolutionLibrary {
  removeLocalStorageKeys(STORAGE_KEY, ...LEGACY_STORAGE_KEYS);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("home-safety-solutions-updated"));
  }
  return DEFAULT_SOLUTION_LIBRARY;
}

export function newSolutionId(section: string): string {
  const prefix = section
    .split(/\s+/)[0]
    ?.slice(0, 3)
    .toUpperCase() || "LW";
  return `LW-${prefix}-${Date.now().toString(36).slice(-4).toUpperCase()}`;
}

export function solutionsById(library: SolutionLibrary): Map<string, SafeHomeSolution> {
  return new Map(library.solutions.map((s) => [s.id, s]));
}

export function solutionsForRubricItem(
  library: SolutionLibrary,
  itemId: string,
): SafeHomeSolution[] {
  return library.solutions.filter((s) => s.rubricItemIds.includes(itemId));
}
