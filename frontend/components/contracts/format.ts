import { parseApiTime } from "@/lib/ist";

/** "31 Oct 2026, 3:05 pm" in IST (or just the date). */
export function formatIst(iso: string | null | undefined, withTime = true): string {
  if (!iso) return "";
  const d = parseApiTime(iso);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "numeric", minute: "2-digit" } : {}),
    timeZone: "Asia/Kolkata",
  }).format(d);
}
