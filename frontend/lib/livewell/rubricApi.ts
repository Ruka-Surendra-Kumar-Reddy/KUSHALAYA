import type { AssessmentCategory } from "./assessment";
import { api } from "@/lib/api";
import { normalizeRubricWithSources, saveSafetyCategories } from "./rubric";

export async function fetchAdminRubric(): Promise<AssessmentCategory[]> {
  const payload = await api<{ categories: AssessmentCategory[] }>("/api/v1/home-safety/rubric");
  const categories = payload.categories ?? [];
  // Empty tenant config is authoritative — clear local cache so UI does not keep factory/stale rubric.
  saveSafetyCategories(categories);
  if (!categories.length) return [];
  return normalizeRubricWithSources(categories);
}

export async function saveAdminRubric(categories: AssessmentCategory[]): Promise<AssessmentCategory[]> {
  const saved = await api<{ categories: AssessmentCategory[] }>("/api/v1/home-safety/rubric", {
    method: "PUT",
    body: JSON.stringify({ categories }),
  });
  saveSafetyCategories(saved.categories ?? categories);
  return normalizeRubricWithSources(saved.categories ?? categories);
}
