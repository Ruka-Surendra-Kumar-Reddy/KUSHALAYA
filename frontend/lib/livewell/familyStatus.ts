/**
 * The one-line status at the top of the family home page:
 * "Lakshmi is well · last visit Wed 7 Oct by Anita · 4/4 checks OK".
 */

import { familyDate } from "./familyTime";

export type FamilyStatusTone = "ok" | "watch" | "alert";

export type FamilyStatusInput = {
  elderFirst: string;
  /** The signed-in person is the elder: "You are well". */
  isSelf?: boolean;
  /** KushLife status text ("Watching", "Calling you", …). */
  klStatus?: string | null;
  /** Care status level from the API. */
  level?: string | null;
  lastVisitAt?: string | null;
  staffName?: string | null;
  /** The latest KushLife visit's checks. */
  checks?: Record<string, "ok" | "concern"> | null;
  /** What the carer noted on the latest visit ("Slept poorly"), from the server status. */
  changes?: string[] | null;
  tz?: string | null;
  now?: Date;
};

export function familyStatusTone(klStatus?: string | null, level?: string | null): FamilyStatusTone {
  const s = (klStatus || "").toLowerCase();
  if (s.includes("calling") || level === "urgent") return "alert";
  if (s.includes("watching") || level === "needs_attention") return "watch";
  return "ok";
}

export function familyStatusLine(input: FamilyStatusInput): { text: string; tone: FamilyStatusTone } {
  const name = input.elderFirst || "Your parent";
  const self = !!input.isSelf;
  const tone = familyStatusTone(input.klStatus, input.level);
  const lead =
    tone === "alert"
      ? (input.klStatus || "").toLowerCase().includes("calling")
        ? self
          ? "We'd like to check on you — we're calling"
          : `${name} needs a check — we're calling you`
        : self
          ? "Your care team needs to check on you"
          : `${name} needs attention`
      : tone === "watch"
        ? `Your care team is keeping a close eye on ${self ? "you" : name}`
        : self
          ? "You are well"
          : `${name} is well`;
  // One status word everywhere: Details and the digest say "Small changes noted"
  // when the carer noted something, so Home says it too.
  const smallChanges =
    tone === "ok" &&
    ((input.changes ?? []).some(Boolean) || /small changes/i.test(input.klStatus || ""));
  const bits = [smallChanges ? `${lead} · small changes noted` : lead];
  if (input.lastVisitAt) {
    const by = input.staffName ? ` by ${input.staffName.trim().split(/\s+/)[0]}` : "";
    bits.push(`last visit ${familyDate(input.lastVisitAt, { tz: input.tz, now: input.now })}${by}`);
  } else {
    bits.push("no visit yet");
  }
  const vals = input.checks ? Object.values(input.checks) : [];
  // Never "4/4 checks OK" on its own when the carer noted something.
  const noted = (input.changes ?? []).filter(Boolean).map((c) => c.charAt(0).toLowerCase() + c.slice(1));
  if (vals.length) {
    const ok = vals.filter((v) => v === "ok").length;
    bits.push(`${ok}/${vals.length} checks OK${noted.length ? ` · ${noted.join(", ")}` : ""}`);
  } else if (noted.length) {
    bits.push(`noted: ${noted.join(", ")}`);
  }
  return { text: bits.join(" · "), tone };
}

/**
 * The server's status word in the same words as Home's line: "Small changes
 * noted" -> "Well · small changes noted", "All good" -> "Well".
 */
export function statusWords(word: string | null | undefined): string {
  const w = (word || "").trim();
  if (!w || /^all good$/i.test(w)) return "Well";
  if (/^small changes noted$/i.test(w)) return "Well · small changes noted";
  return w;
}

/**
 * A visit's check line with what the carer noted, from the same status
 * (GET /family/status): "KushLife check: Safe ✓ · … · noted: slept poorly, ate less".
 * Never all ticks on their own when the status says otherwise.
 */
export function withNotedChanges(text: string | null | undefined, changes: string[] | null | undefined): string {
  const t = (text || "").trim();
  const noted = (changes ?? []).filter(Boolean).map((c) => c.charAt(0).toLowerCase() + c.slice(1));
  if (!noted.length || /\bnoted\b/i.test(t)) return t;
  // "All four checks as usual" is no longer true: say what was noted instead.
  if (/all four (?:kushlife )?checks as usual/i.test(t)) {
    return t.replace(/all four (?:kushlife )?checks as usual\.?/i, `noted ${noted.join(", ")}.`);
  }
  const lines = t.split("\n");
  lines[0] = `${lines[0]}${lines[0] ? " · " : ""}noted: ${noted.join(", ")}`;
  return lines.join("\n");
}

/** Is this visit the one GET /family/status describes (posted within 6 hours of it)? */
export function isStatusVisit(at: string | null | undefined, statusVisitAt: string | null | undefined): boolean {
  const a = at ? Date.parse(at) : NaN;
  const b = statusVisitAt ? Date.parse(statusVisitAt) : NaN;
  return Number.isFinite(a) && Number.isFinite(b) && Math.abs(a - b) <= 6 * 3600 * 1000;
}

/** Request tracker steps on Requests: requested → quoted → booked → done. */
export const REQUEST_STEPS = ["Requested", "Quoted", "Booked", "Done"] as const;

/**
 * Which step a service request has reached (0–3), from its existing status and
 * quote/payment fields; null for cancelled or declined requests (no tracker).
 */
export function requestStep(r: {
  status: string;
  quoted_amount_minor?: number | null;
  payment_status?: string | null;
}): number | null {
  const s = (r.status || "").toLowerCase();
  if (s === "cancelled" || s === "declined") return null;
  if (s === "done" || s === "completed") return 3;
  if (s === "confirmed" || s === "scheduled" || s === "booked") return 2;
  const pay = (r.payment_status || "").toLowerCase();
  if ((r.quoted_amount_minor ?? 0) > 0 || pay === "awaiting_approval" || pay === "paid") return 1;
  return 0;
}

/**
 * Emergency contacts a family member should call: never the senior themself
 * ("Senior (at home)" is not a local person to call for them).
 */
export function contactsToCall<T extends { name: string; relationship?: string | null }>(
  contacts: T[],
  seniorName: string,
): T[] {
  const senior = (seniorName || "").trim().toLowerCase();
  return contacts.filter((c) => {
    const name = (c.name || "").trim().toLowerCase();
    if (senior && name === senior) return false;
    return !/^\s*(senior|self|client)\b/i.test(c.relationship || "");
  });
}
