/**
 * Products carry two category spellings (old seeded "Bathroom Safety", "Living Room",
 * "Kushalaya Services" and the editor's short list). Stored values stay as they are;
 * this only merges them for display, filtering and grouping.
 */
export const PRODUCT_CATEGORIES = ["Bathroom", "Bedroom", "Living room", "Kitchen", "Wearable", "Service", "Other"];

export function canonicalCategory(raw: string | null | undefined): string {
  const c = (raw || "").trim();
  if (!c) return "";
  const k = c.toLowerCase().replace(/\s+/g, " ");
  if (/services?$/.test(k)) return "Service";
  const base = k.replace(/ safety$/, "");
  const hit = PRODUCT_CATEGORIES.find((x) => x.toLowerCase() === base || `${x.toLowerCase()}s` === base);
  return hit || c;
}

export type CategoryGroup<T> = { category: string; items: T[] };

/** Group items by display category, in the editor's order, unknown ones after, "No category" last. */
export function groupByCategory<T>(items: T[], categoryOf: (item: T) => string | null | undefined): CategoryGroup<T>[] {
  const map = new Map<string, T[]>();
  for (const item of items) {
    const key = canonicalCategory(categoryOf(item)) || "No category";
    map.set(key, [...(map.get(key) || []), item]);
  }
  const rank = (k: string) => {
    if (k === "No category") return 1000;
    const i = PRODUCT_CATEGORIES.indexOf(k);
    return i >= 0 ? i : 500;
  };
  return Array.from(map.entries())
    .sort((a, b) => rank(a[0]) - rank(b[0]) || a[0].localeCompare(b[0]))
    .map(([category, list]) => ({ category, items: list }));
}
