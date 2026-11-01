/**
 * Staff-facing labels for home safety assessments. Assessment ids
 * ("hsa-1784559753603-l3qdo0e") are internal keys — keep them in values/URLs,
 * never as visible text.
 */

const ASSESSMENT_ID_SUFFIX = /\s*\((?:hsa|hs|lwa)-[0-9a-z-]+\)/gi;

/** "Bathroom photo (hsa-1784559753603-l3qdo0e)" → "Bathroom photo". */
export function stripAssessmentIdSuffix(name: string | null | undefined): string {
  const raw = name || "";
  const cleaned = raw.replace(ASSESSMENT_ID_SUFFIX, "").trim();
  return cleaned || raw;
}

const STATUS_WORD: Record<string, string> = {
  completed: "Completed",
  draft: "Draft",
  in_progress: "In progress",
  archived: "Archived",
};

export function assessmentStatusWord(status: string | null | undefined): string {
  const s = (status || "").toLowerCase();
  if (STATUS_WORD[s]) return STATUS_WORD[s];
  const t = s.replace(/_/g, " ");
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : "Draft";
}

/** "2026-08-06T10:00:00" → "6 Aug 2026" (IST; naive backend times are UTC). */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const hasZone = /[zZ]$|[+-]\d\d:?\d\d$/.test(iso);
  const d = new Date(hasZone || !iso.includes("T") ? iso : `${iso}Z`);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" });
}

export type AssessmentOptionInput = {
  status?: string | null;
  completed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  assessor?: string | null;
};

/** "Home safety assessment · 6 Aug 2026 · Completed · by Ravi Kumar". */
export function assessmentOptionLabel(a: AssessmentOptionInput): string {
  const parts = ["Home safety assessment"];
  const when = shortDate(a.completed_at || a.created_at || a.updated_at);
  if (when) parts.push(when);
  parts.push(assessmentStatusWord(a.status));
  const who = (a.assessor || "").trim();
  if (who) parts.push(`by ${who}`);
  return parts.join(" · ");
}

/** Score is only final once the assessment is completed. */
export function isScoreFinal(status: string | null | undefined): boolean {
  return status === "completed";
}

/** Shown instead of a score/band while an assessment is still being filled in. */
export function draftScoreText(percentRated: number): string {
  const pct = Math.max(0, Math.min(100, Math.round(Number(percentRated) || 0)));
  return `Draft · ${pct}% rated`;
}

/** Whole years from a "YYYY-MM-DD" date of birth (IST today). Blank or bad input → "". */
export function ageFromDob(dob: string | null | undefined, today = new Date()): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec((dob || "").trim());
  if (!m) return "";
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const ist = new Date(today.getTime() + 5.5 * 3_600_000);
  let age = ist.getUTCFullYear() - y;
  if (ist.getUTCMonth() + 1 < mo || (ist.getUTCMonth() + 1 === mo && ist.getUTCDate() < d)) age -= 1;
  return age > 0 && age < 130 ? String(age) : "";
}

/** Page title for an assessment: the client's name, or "Draft · 6 Aug 2026" for an unnamed draft. */
export function assessmentTitle(name: string | null | undefined, createdAt: string | null | undefined): string {
  const n = (name || "").trim();
  if (n) return n;
  const when = shortDate(createdAt);
  return when ? `Draft · ${when}` : "Draft assessment";
}
