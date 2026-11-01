/**
 * Register a portal service worker — and make the browser forget any older one.
 *
 * Browsers only swap in a new worker after their own update check, so a user
 * who had the old family worker (the one that proxied navigations and made
 * Chrome render a 307's body as a blank page) kept it for a page load or two
 * after the fix shipped, and a hard refresh did not reliably clear it either.
 * This runs on every portal page load and is idempotent:
 *
 *  1. unregister every registration on this origin whose script is not
 *     exactly the one we want (old version, or the other portal's worker);
 *  2. delete every CacheStorage cache — nothing is cached by design any more;
 *  3. register the current worker (`updateViaCache: "none"` so the script
 *     itself is never served from the HTTP cache).
 *
 * The versioned URL is what tells old from new, so bump `version` together
 * with the worker's CACHE constant on every change (see CLAUDE.md).
 */
export async function registerPortalWorker(scriptPath: string, version: string): Promise<void> {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) return;
  const want = `${scriptPath}?v=${version}`;
  try {
    const registrations = await navigator.serviceWorker.getRegistrations();
    for (const reg of registrations) {
      const script =
        reg.active?.scriptURL || reg.waiting?.scriptURL || reg.installing?.scriptURL || "";
      if (!script.endsWith(want)) await reg.unregister();
    }
    if ("caches" in window) {
      const keys = await caches.keys();
      await Promise.all(keys.map((key) => caches.delete(key)));
    }
    await navigator.serviceWorker.register(want, { updateViaCache: "none" });
  } catch {
    /* the worker is optional — the portal works without it */
  }
}
