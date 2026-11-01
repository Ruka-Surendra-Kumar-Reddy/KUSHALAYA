/** Read localStorage with SafeHome key first, then legacy ElderCare bootstrap keys. */
export function readLocalStorageWithLegacy(
  key: string,
  legacyKeys: string[],
): string | null {
  if (typeof window === "undefined") return null;
  const current = localStorage.getItem(key);
  if (current != null) return current;
  for (const legacy of legacyKeys) {
    const raw = localStorage.getItem(legacy);
    if (raw != null) return raw;
  }
  return null;
}

export function removeLocalStorageKeys(...keys: string[]): void {
  if (typeof window === "undefined") return;
  for (const key of keys) localStorage.removeItem(key);
}
