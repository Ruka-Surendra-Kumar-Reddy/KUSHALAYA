/**
 * Visit-report rules for families: which reports ask for a rating / NPS.
 */

/** How long after a care visit the family is asked to rate it. */
export const RATE_WITHIN_DAYS = 14;

type VisitLike = { id: string; visit_type?: string | null; status?: string | null; visited_at?: string | null };

/** A completed care visit (a caregiver job), not an assessment or the baseline profile visit. */
export function isCompletedCareVisit(v: VisitLike): boolean {
  return (
    String(v.id || "").startsWith("job-") &&
    String(v.status || "").toLowerCase() === "completed" &&
    !/assess|baseline|profile/i.test(v.visit_type || "")
  );
}

/** Rating is asked on completed care visits from the last 14 days only. */
export function canAskRating(v: VisitLike, now: number = Date.now()): boolean {
  if (!isCompletedCareVisit(v)) return false;
  const at = Date.parse(v.visited_at || "");
  return Number.isFinite(at) && now - at <= RATE_WITHIN_DAYS * 24 * 3600 * 1000;
}
