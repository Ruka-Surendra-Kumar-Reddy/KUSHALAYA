/**
 * Dashboard "Today's run sheet" rules, shared with Visits and the caregiver app
 * so every screen flags the same visits.
 */

export const STALE_CHECK_IN_HOURS = 12;
export const REPLY_OVERDUE_HOURS = 24;
const HOUR = 3_600_000;

type JobLike = {
  status: string;
  checked_in_at?: string | null;
  started_at?: string | null;
  scheduled_at?: string | null;
};

/** An arrival earlier than this before the booked time belongs to an older booking (rescheduled). */
const EARLY_ARRIVAL_HOURS = 3;

/**
 * The arrival (or set-off) time to show, or null when it can't belong to this
 * booking: a visit rebooked after a check-in must not read "arrived" days before "booked".
 */
export function arrivalAt(j: JobLike): string | null {
  const at = j.checked_in_at || j.started_at || null;
  if (!at) return null;
  if (!j.scheduled_at) return at;
  const t = new Date(at).getTime();
  const booked = new Date(j.scheduled_at).getTime();
  if (!Number.isFinite(t) || !Number.isFinite(booked)) return at;
  return t < booked - EARLY_ARRIVAL_HOURS * HOUR ? null : at;
}

/** When the caregiver arrived (or set off); falls back to the booked time. */
export function startedAt(j: JobLike): string | null {
  return arrivalAt(j) || j.scheduled_at || j.checked_in_at || j.started_at || null;
}

/** One label for a stale visit everywhere: "Not closed · 4 days". */
export function staleLabel(j: JobLike, now = Date.now()): string {
  const at = startedAt(j);
  const t = at ? new Date(at).getTime() : NaN;
  if (!Number.isFinite(t)) return "Not closed";
  return `Not closed · ${waitLabel(Math.max(0, Math.floor((now - t) / HOUR)))}`;
}

/** Checked in (or on the way) more than 12 hours ago and never finished: "Not closed". */
export function isStaleCheckIn(j: JobLike, now = Date.now()): boolean {
  if (j.status !== "checked_in" && j.status !== "on_the_way") return false;
  const at = startedAt(j);
  if (!at) return false;
  const t = new Date(at).getTime();
  return Number.isFinite(t) && now - t > STALE_CHECK_IN_HOURS * HOUR;
}

/** Hours a family has waited since its last message (0 when unknown). */
export function hoursWaiting(lastAt: string | null | undefined, now = Date.now()): number {
  if (!lastAt) return 0;
  const t = new Date(lastAt).getTime();
  return Number.isFinite(t) ? Math.max(0, Math.floor((now - t) / HOUR)) : 0;
}

/** A family message still unanswered after 24 hours. */
export function isReplyOverdue(lastAt: string | null | undefined, now = Date.now()): boolean {
  return hoursWaiting(lastAt, now) >= REPLY_OVERDUE_HOURS;
}

/** "5 h" under a day, then "3 days". */
export function waitLabel(hours: number): string {
  if (hours < 24) return `${hours} h`;
  const d = Math.floor(hours / 24);
  return `${d} day${d === 1 ? "" : "s"}`;
}

/** "1 caregiver", "2 caregivers". */
export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}
