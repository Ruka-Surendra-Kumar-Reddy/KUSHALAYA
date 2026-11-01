/**
 * Times for families abroad: everything happens in Hyderabad, so inputs mean India time (IST)
 * and every time is shown in IST, with the viewer's own time added when it differs.
 */

const IST = "Asia/Kolkata";

const NAIVE_DATETIME = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/;

/**
 * An API timestamp → Date. The server stores UTC; a value with no zone ("2026-10-28T07:11:00")
 * is UTC, not the browser's local time (that bug showed 12:41 IST as 7:11 IST).
 */
export function parseApiTime(iso: string | Date): Date {
  if (iso instanceof Date) return iso;
  const s = iso.trim();
  return new Date(NAIVE_DATETIME.test(s) ? `${s.replace(" ", "T")}Z` : s);
}

/** A `datetime-local` value typed as India time ("2026-10-09T10:00") → ISO with the IST offset. */
export function istInputToISO(value: string): string {
  return `${value.length === 16 ? `${value}:00` : value}+05:30`;
}

function viewerZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || IST;
  } catch {
    return IST;
  }
}

/** "Thu 9 Oct, 11:00 am IST (9:30 am your time)"; the bracket only when the viewer isn't in India. */
export function formatIST(iso: string | null | undefined, opts: { dateOnly?: boolean } = {}): string {
  if (!iso) return "";
  const d = parseApiTime(iso);
  if (Number.isNaN(d.getTime())) return "";
  const base: Intl.DateTimeFormatOptions = opts.dateOnly
    ? { weekday: "short", day: "numeric", month: "short" }
    : { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" };
  const ist = d.toLocaleString("en-IN", { ...base, timeZone: IST });
  if (opts.dateOnly) return ist;
  const zone = viewerZone();
  const offset = (tz: string) => d.toLocaleString("en-US", { timeZone: tz, hour: "numeric", minute: "2-digit", hour12: false });
  if (zone === IST || offset(zone) === offset(IST)) return `${ist} IST`;
  const day = (tz: string) => d.toLocaleDateString("en-IN", { timeZone: tz, day: "numeric" });
  const mine = d.toLocaleString("en-IN", {
    // Show the weekday too when it's a different day where the viewer is.
    ...(day(zone) !== day(IST) ? { weekday: "short" } : {}),
    hour: "numeric",
    minute: "2-digit",
    timeZone: zone,
  });
  return `${ist} IST (${mine} your time)`;
}

/** "YYYY-MM-DDTHH:MM" for a datetime-local input, in India time, `addMs` from now. */
export function istInputValue(addMs = 0): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: IST,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(Date.now() + addMs));
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "00";
  return `${get("year")}-${get("month")}-${get("day")}T${get("hour")}:${get("minute")}`;
}

/** "India", "New York", "Tokyo": a readable place name for an IANA zone (never the raw "Asia/Tokyo"). */
export function zonePlace(tz: string | null | undefined): string {
  if (!tz || tz === IST || tz === "Asia/Calcutta") return "India";
  const city = tz.split("/").pop() || tz;
  return city.replace(/_/g, " ");
}

const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "28 Sep" (always three-letter months, unlike en-IN/en-GB's "Sept"); `weekday` adds "Mon ". */
export function dayMonth(d: Date, tz: string = IST, weekday = false): string {
  const parts = new Intl.DateTimeFormat("en-US", { timeZone: tz, day: "numeric", month: "numeric", weekday: "short" }).formatToParts(d);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${weekday ? `${get("weekday")} ` : ""}${get("day")} ${MON[Number(get("month")) - 1] ?? ""}`;
}

/** A "YYYY-MM-DD" (India date) as "28 Sep". */
export function isoDay(ymd: string): string {
  const d = new Date(`${ymd.slice(0, 10)}T12:00:00+05:30`);
  return Number.isNaN(d.getTime()) ? ymd : dayMonth(d);
}

/** A week starting on "YYYY-MM-DD" (Monday, India date): "28 Sep – 4 Oct". */
export function weekRange(start: string, end?: string): string {
  const s = new Date(`${start.slice(0, 10)}T12:00:00+05:30`);
  if (Number.isNaN(s.getTime())) return start;
  const e = end ? new Date(`${end.slice(0, 10)}T12:00:00+05:30`) : new Date(s.getTime() + 6 * 86400000);
  return `${dayMonth(s)} – ${dayMonth(e)}`;
}

/**
 * Family-facing time in the family member's own zone (from My details): "Fri 9 Oct, 1:00 am New York time".
 * Without a zone (or an invalid one) it stays in India time and says so.
 */
export function formatInZone(iso: string | null | undefined, tz?: string | null): string {
  if (!iso) return "";
  const d = parseApiTime(iso);
  if (Number.isNaN(d.getTime())) return "";
  const at = (zone: string) =>
    `${dayMonth(d, zone, true)}, ${d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: zone }).toLowerCase()}`;
  if (tz && tz !== IST && tz !== "Asia/Calcutta") {
    try {
      return `${at(tz)} ${zonePlace(tz)} time`;
    } catch {
      /* unknown zone: fall through to India time */
    }
  }
  return `${at(IST)} India time`;
}

/** The one ops clock format: "10:00 am" (12-hour, lower-case, India time). */
export function timeIST(iso: string | Date | null | undefined): string {
  if (!iso) return "";
  const d = parseApiTime(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d
    .toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true, timeZone: IST })
    .replace(/\s?(AM|PM)$/i, (_m, ap: string) => ` ${ap.toLowerCase()}`);
}

/** "Thu 8 Oct, 10:00 am" in India time (no seconds); `year` adds the year for old records. */
export function dateTimeIST(iso: string | Date | null | undefined, opts: { year?: boolean } = {}): string {
  if (!iso) return "";
  const d = parseApiTime(iso);
  if (Number.isNaN(d.getTime())) return "";
  const y = opts.year ? ` ${d.toLocaleDateString("en-US", { year: "numeric", timeZone: IST })}` : "";
  return `${dayMonth(d, IST, true)}${y}, ${timeIST(d)}`;
}

/** True when the instant falls on today's India date. */
export function isTodayIST(iso: string | Date | null | undefined): boolean {
  if (!iso) return false;
  const d = parseApiTime(iso);
  const day = (x: Date) => x.toLocaleDateString("en-CA", { timeZone: IST });
  return !Number.isNaN(d.getTime()) && day(d) === day(new Date());
}

/** "10:00 am" today, otherwise "Thu 8 Oct, 10:00 am". */
export function whenIST(iso: string | Date | null | undefined): string {
  return isTodayIST(iso) ? timeIST(iso) : dateTimeIST(iso);
}

/** One greeting for every portal, by the hour in India (not the device clock). */
export function greetingIST(now: Date = new Date()): string {
  const h = Number(now.toLocaleString("en-US", { hour: "numeric", hourCycle: "h23", timeZone: "Asia/Kolkata" })) % 24;
  if (h < 5) return "Good night";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}
