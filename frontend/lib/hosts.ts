/**
 * Which public host a request arrived on. Used by `middleware.ts` to decide
 * between the family portal, the marketing site and the ops portal.
 *
 * Checks are exact hostnames on purpose: a `startsWith("family.")` rule once
 * served the marketing site on the family subdomain. Every environment that
 * fronts this app therefore has to be listed here — production, staging and
 * the `*.localhost` names used by `next dev`.
 *
 * Staging (`staging-*.kushalaya.com`, see deploy/nginx/staging.kushalaya.com.conf
 * and scripts/deploy/install-staging.sh) routes exactly like production:
 * staging-family -> family portal, staging-www -> marketing, staging-ops -> ops.
 */

export const FAMILY_HOSTS: ReadonlySet<string> = new Set([
  "family.kushalaya.com",
  "staging-family.kushalaya.com",
  "test-family.kushalaya.com",
  "family.localhost",
]);

export const MARKETING_HOSTS: ReadonlySet<string> = new Set([
  "www.kushalaya.com",
  "kushalaya.com",
  "staging-www.kushalaya.com",
  "test.kushalaya.com",
  "kushalaya.localhost",
  // The old *.tekmatrix.ai hostnames used to be listed here as a safety net.
  // They are gone: those vhosts now 301 to the kushalaya.com equivalents in
  // nginx, so a request with one of those Host headers never reaches this
  // code. Re-adding them would only reintroduce the old brand.
]);

/** Caregiver field app host (11 Oct 2026). Served by the ops app; see middleware. */
export const CAREGIVER_HOSTS: ReadonlySet<string> = new Set([
  "caregiver.kushalaya.com",
  "staging-caregiver.kushalaya.com",
  "test-caregiver.kushalaya.com",
  "caregiver.localhost",
]);

/** Lower-cased hostname without the port. */
export function hostname(host: string): string {
  return host.toLowerCase().split(":")[0];
}

/**
 * Family portal host. Families get their own subdomain so they never see an
 * "ops" URL, and so the brand name is not repeated in the path
 * (ops.kushalaya.com/kushalaya/family/login).
 *
 * `/login` here serves the family portal's own login, NOT the staff one.
 */
export function isFamilyHost(host: string): boolean {
  return FAMILY_HOSTS.has(hostname(host));
}

/** Public marketing host — serves / as /marketing. Ops is on ops.kushalaya.com. */
export function isMarketingHost(host: string): boolean {
  // Checked first: family.kushalaya.com is NOT marketing, whatever else is
  // ever added to MARKETING_HOSTS.
  if (isFamilyHost(host)) return false;
  return MARKETING_HOSTS.has(hostname(host));
}

/** caregiver.kushalaya.com — the ops app, kept to the caregiver field app. */
export function isCaregiverHost(host: string): boolean {
  return CAREGIVER_HOSTS.has(hostname(host));
}

/** Anything that is neither family nor marketing is the ops portal. */
export function isOpsHost(host: string): boolean {
  return !isFamilyHost(host) && !isMarketingHost(host);
}
