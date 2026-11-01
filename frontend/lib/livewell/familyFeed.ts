/**
 * Updates feed for families: one card per visit, showing its latest state.
 *
 * Visit notices carry no job id, so a visit is recognised by its title and
 * the day in the text ("Care visit scheduled" / "updated" / "cancelled" with
 * "… on Sat 17 Oct …"). "X is on the way" / "has arrived" join the chain of
 * the same visit title.
 */

import { isBackdatedSchedule, mentionedDay } from "./familyTime";
import type { FamilyMessage } from "./familyApi";

type FeedItem = { id: string; kind: string; title: string; body: string; created_at: string | null };

const SCHEDULE_RE = /^(.+?)\s+(scheduled|updated|cancelled|completed)\b/i;
const LIVE_RE = /^(\S+)\s+(is on the way|has arrived)\b/i;

const DAY = 24 * 3600 * 1000;

function ts(v: string | null): number {
  const t = v ? Date.parse(v) : NaN;
  return Number.isFinite(t) ? t : 0;
}

function dayKey(d: Date | null): string {
  return d ? d.toISOString().slice(0, 10) : "";
}

/** "Anita is on the way for the care visit." -> "care visit". */
function liveTitle(body: string): string {
  const m = (body || "").match(/for the ([^.]+?)\.?$/i) || (body || "").match(/for the ([^.]+)/i);
  return (m?.[1] || "").trim().toLowerCase();
}

/**
 * - Drops "scheduled" notices for a day already past when they were posted.
 * - Keeps only the newest scheduled / updated / cancelled / completed notice
 *   for the same visit (title + day).
 * - Drops "on the way" more than a day before the visit it belongs to, and
 *   "on the way" / "has arrived" once a later notice for that visit exists.
 * Input order is kept (the API sends newest first).
 */
export function collapseVisitChains<T extends FeedItem>(items: T[]): T[] {
  const kept = items.filter((r) => !isBackdatedSchedule(r.title, r.created_at, r.body));
  const newestByKey = new Map<string, T>();
  const visitDays: { title: string; day: number }[] = [];
  for (const r of kept) {
    const m = r.title.match(SCHEDULE_RE);
    if (!m) continue;
    const posted = new Date(ts(r.created_at));
    const when = mentionedDay(`${r.title} ${r.body}`, posted);
    const title = m[1].trim().toLowerCase();
    if (when) visitDays.push({ title, day: when.getTime() });
    const key = `${title}|${dayKey(when) || r.id}`;
    const cur = newestByKey.get(key);
    if (!cur || ts(r.created_at) > ts(cur.created_at)) newestByKey.set(key, r);
  }
  return kept.filter((r) => {
    const m = r.title.match(SCHEDULE_RE);
    if (m) {
      const when = mentionedDay(`${r.title} ${r.body}`, new Date(ts(r.created_at)));
      const key = `${m[1].trim().toLowerCase()}|${dayKey(when) || r.id}`;
      return newestByKey.get(key) === r;
    }
    const live = r.title.match(LIVE_RE);
    if (!live) return true;
    const title = liveTitle(r.body);
    const at = ts(r.created_at);
    // The visit this belongs to is more than a day away: an early tap, not news.
    // (Only when we know of a later visit and none on or around that day.)
    const days = visitDays.filter((v) => v.title === title).map((v) => v.day);
    const early = days.some((d) => d - at > DAY) && !days.some((d) => Math.abs(d - at) <= DAY * 1.5);
    if (early && /on the way/i.test(live[2])) return false;
    // A later notice about the same visit (arrived / completed) says it better.
    const later = kept.some((o) => {
      if (o === r) return false;
      const t = ts(o.created_at);
      if (t <= at || t - at > DAY / 2) return false;
      const om = o.title.match(LIVE_RE);
      if (om) return liveTitle(o.body) === title && /has arrived/i.test(om[2]) && /on the way/i.test(live[2]);
      const sm = o.title.match(SCHEDULE_RE);
      return !!sm && sm[1].trim().toLowerCase() === title;
    });
    return !later;
  });
}

const REPORT_RE = /^(.+?)\s+report$/i;

/**
 * One card per visit: the "<visit> report" notice is dropped when the visit's
 * own card (same title, posted within 6 hours) is in the feed; that card links
 * to the full report and carries the same checks.
 */
export function mergeVisitReports<T extends FeedItem>(items: T[]): T[] {
  const visits = items.filter((r) => r.kind === "visit");
  return items.filter((r) => {
    if (r.kind === "visit") return true;
    const m = r.title.match(REPORT_RE);
    if (!m) return true;
    const title = m[1].trim().toLowerCase();
    const at = ts(r.created_at);
    return !visits.some((v) => v.title.trim().toLowerCase() === title && Math.abs(ts(v.created_at) - at) <= DAY / 4);
  });
}

const MISSED_RE = /didn[’']t happen|did not happen|was missed/i;

/**
 * A missed-visit notice promises "will call you today". Shown on a later day,
 * or posted long after the visit it is about, "today" is no longer true.
 */
export function tidyMissedVisits<T extends FeedItem>(items: T[], now: Date = new Date()): T[] {
  return items.map((r) => {
    if (!MISSED_RE.test(r.title) || !/\bcall you today\b/i.test(r.body || "")) return r;
    const posted = new Date(ts(r.created_at));
    const visitDay = mentionedDay(`${r.title} ${r.body}`, posted);
    const late = !!visitDay && posted.getTime() - visitDay.getTime() > DAY * 1.5;
    const later = posted.toDateString() !== now.toDateString();
    return late || later ? { ...r, body: r.body.replace(/\bcall you today\b/i, "call you") } : r;
  });
}

/**
 * "Intro:\n- one\n- two\nYour care team will call you." -> intro, list items and
 * the closing sentence as its own paragraph (it used to run on from the last
 * item: "… — needs fixing Your care team will call you").
 */
export function splitFeedBody(text: string): { intro: string; items: string[]; outro: string } {
  const parts = text.split(/(?:^|\n|\s)[-•–]\s+/);
  if (parts.length < 3) return { intro: text, items: [], outro: "" };
  const [intro, ...rest] = parts;
  const items = rest.map((t) => t.trim()).filter(Boolean);
  if (items.length < 2) return { intro: text, items: [], outro: "" };
  let outro = "";
  const last = items[items.length - 1];
  const nl = last.indexOf("\n");
  if (nl >= 0) {
    outro = last.slice(nl + 1).trim();
    items[items.length - 1] = last.slice(0, nl).trim();
  } else {
    // Joined without a line break: a new sentence starting "Your …" / "We …" / "Our …" / "Please …".
    const m = last.match(/^(.*?)(?:\.\s+|\s+)((?:Your|We|We'll|Our|Please|They|You)\b.*)$/);
    if (m && m[1].trim()) {
      items[items.length - 1] = m[1].trim();
      outro = m[2].trim();
    }
  }
  return { intro: intro.trim(), items, outro };
}

/**
 * Team messages that answer something this family asked (a team message
 * after a family message), newest first, at most `limit`. A greeting the
 * team posted on its own is left to the Messages page.
 */
export function teamReplies(rows: FamilyMessage[], limit = 3): FamilyMessage[] {
  const sorted = [...rows].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
  const out: FamilyMessage[] = [];
  let asked = false;
  for (const m of sorted) {
    if (m.sender_role === "family") asked = true;
    else if (m.sender_role === "team" && asked) out.push(m);
  }
  return out.reverse().slice(0, limit);
}
