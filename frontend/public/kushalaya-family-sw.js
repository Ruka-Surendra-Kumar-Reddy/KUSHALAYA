/* Safe Home family PWA worker.
 *
 * This worker deliberately has NO fetch handler. It used to proxy navigations
 * (network-first, cache fallback), and that broke every server redirect for
 * anyone who had it installed: when the server answered `/` with a 307, the
 * response came back through the worker and Chrome rendered the 307's HTML
 * body — an empty shell with just the copyright line — instead of following
 * it, and the page only moved on via the client-side redirect embedded in
 * that shell. First visits (no worker yet) were unaffected, which is why the
 * bug only showed for returning users.
 *
 * The offline fallback it provided was never real (every portal page needs
 * the API), so nothing is lost. The worker now exists only so the portal is
 * installable; without a fetch handler Chrome also skips starting it for
 * navigations, which is faster.
 *
 * Bump CACHE and the `?v=` in FamilyPwaRegister together on every change.
 */
const CACHE = "kushalaya-family-v7";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      // Drop everything, including this worker's own name: nothing is cached any more.
      .then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});
