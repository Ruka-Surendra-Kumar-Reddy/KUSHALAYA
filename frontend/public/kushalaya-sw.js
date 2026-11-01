/* Safe Home assessor PWA worker — only the assessor app, never the admin portal.
 *
 * No fetch handler on purpose. Proxying navigations through a worker breaks
 * server redirects for installed users (Chrome renders a 307's body instead
 * of following it — see kushalaya-family-sw.js for the full story), and the
 * assessor app needs the API for anything useful, so the cache fallback never
 * bought real offline use. The worker exists only so the app is installable.
 *
 * Bump CACHE and the `?v=` in HomeSafetyPwaRegister together on every change.
 */
const CACHE = "kushalaya-assessor-v10";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});
