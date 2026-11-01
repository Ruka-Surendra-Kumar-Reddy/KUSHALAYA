/**
 * One date and time format for the family portal.
 * Dates: "Wed 7 Oct" / "7 Oct" (three-letter months, no leading zero).
 * Times: in the family's own zone (My details), with IST in brackets when it differs.
 */

export const IST_ZONE = "Asia/Kolkata";
const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function toDate(v: string | Date | null | undefined): Date | null {
  if (!v) return null;
  const d = v instanceof Date ? v : new Date(v);
  return Number.isNaN(d.getTime()) ? null : d;
}

function safeZone(tz: string | null | undefined): string {
  if (!tz) return IST_ZONE;
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: tz });
    return tz === "Asia/Calcutta" ? IST_ZONE : tz;
  } catch {
    return IST_ZONE;
  }
}

function parts(d: Date, tz: string) {
  const p = new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    weekday: "short",
    day: "numeric",
    month: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).formatToParts(d);
  const get = (t: string) => p.find((x) => x.type === t)?.value ?? "";
  return {
    weekday: get("weekday"),
    day: get("day"),
    month: MON[Number(get("month")) - 1] ?? "",
    year: get("year"),
    time: `${get("hour")}:${get("minute")} ${get("dayPeriod").toLowerCase()}`,
  };
}

/** "Wed 7 Oct" (or "7 Oct" with weekday=false). A different year is added: "7 Oct 2025". */
export function familyDate(
  v: string | Date | null | undefined,
  opts: { weekday?: boolean; tz?: string | null; now?: Date } = {},
): string {
  const d = toDate(v);
  if (!d) return "";
  const tz = safeZone(opts.tz);
  const p = parts(d, tz);
  const thisYear = parts(opts.now ?? new Date(), tz).year;
  const base = `${opts.weekday === false ? "" : `${p.weekday} `}${p.day} ${p.month}`;
  return p.year && p.year !== thisYear ? `${base} ${p.year}` : base;
}

/** True when the zone shows the same clock time as India at that moment. */
function sameAsIST(d: Date, tz: string): boolean {
  return tz === IST_ZONE || parts(d, tz).time === parts(d, IST_ZONE).time;
}

/**
 * "Wed 7 Oct, 9:30 pm (11:00 am IST)" in the family's zone;
 * "Wed 7 Oct, 11:00 am IST" when they are in India or the zone is unknown.
 */
export function familyTime(
  v: string | Date | null | undefined,
  tz?: string | null,
  opts: { weekday?: boolean; now?: Date } = {},
): string {
  const d = toDate(v);
  if (!d) return "";
  const zone = safeZone(tz);
  const ist = parts(d, IST_ZONE);
  if (sameAsIST(d, zone)) {
    return `${familyDate(d, { ...opts, tz: IST_ZONE })}, ${ist.time} IST`;
  }
  const mine = parts(d, zone);
  // Show the India day too when it differs from the family's day.
  const istDay = mine.day !== ist.day ? `${ist.weekday} ${ist.day} ${ist.month}, ` : "";
  return `${familyDate(d, { ...opts, tz: zone })}, ${mine.time} (${istDay}${ist.time} IST)`;
}

/** Just the clock part: "9:30 pm (11:00 am IST)" or "11:00 am IST". */
export function familyClock(v: string | Date | null | undefined, tz?: string | null): string {
  const d = toDate(v);
  if (!d) return "";
  const zone = safeZone(tz);
  const ist = parts(d, IST_ZONE).time;
  return sameAsIST(d, zone) ? `${ist} IST` : `${parts(d, zone).time} (${ist} IST)`;
}

/** Dates inside stored text, made consistent: "Sat 03 Oct" -> "Sat 3 Oct", "Sept" -> "Sep". */
export function tidyDates(text: string | null | undefined): string {
  return (text || "")
    .replace(/\b0(\d)(\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\b)/g, "$1$2")
    .replace(/\bSept\b\.?/g, "Sep");
}

/** The first "7 Sep" / "17 Oct 2026" in a text, as the end of that IST day; null when none. */
export function mentionedDay(text: string | null | undefined, posted: Date): Date | null {
  const m = (text || "").match(/\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\w*(?:\s+(\d{4}))?/i);
  if (!m) return null;
  const month = MON.findIndex((x) => x.toLowerCase() === m[2].slice(0, 3).toLowerCase());
  const year = m[3] ? Number(m[3]) : Number(parts(posted, IST_ZONE).year);
  return new Date(`${year}-${String(month + 1).padStart(2, "0")}-${m[1].padStart(2, "0")}T23:59:59+05:30`);
}

/**
 * A "… scheduled: Mon 7 Sep" notice posted after that date (backdated by data entry).
 * Families should not see a visit "scheduled" for a day already gone when it was posted.
 */
export function isBackdatedSchedule(
  title: string,
  createdAt: string | null | undefined,
  body?: string | null,
): boolean {
  if (!/scheduled/i.test(title || "") || !createdAt) return false;
  const posted = toDate(createdAt);
  if (!posted) return false;
  // The date is usually in the body ("Care visit on Mon 7 Sep, 10:00 am"), sometimes in the title.
  const when = mentionedDay(title, posted) ?? mentionedDay(body, posted);
  return !!when && when.getTime() < posted.getTime();
}
