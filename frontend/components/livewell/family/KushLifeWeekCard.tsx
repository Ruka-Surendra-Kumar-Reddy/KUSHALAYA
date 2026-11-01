"use client";

import { useEffect, useState } from "react";
import { formatInZone, isoDay } from "@/lib/ist";
import { useFamilyTimezone } from "@/lib/family-zone";
import type { KushLifeWeekCard as Card, WeekShare } from "@/lib/kushlife";
import { familyApi } from "@/lib/livewell/familyApi";

type Week = { card: Card; summary: { text: string; approved_at: string } | null; is_monday: boolean };

const day = isoDay;

/** "2 changes noticed, 1 followed up so far"; never "No changes noticed" when the carer noted some. */
export function changesLine(raised: number, closed: number, noted: string[] = []) {
  if (!raised) return noted.length ? `Noted on the last visit: ${noted.join(", ").toLowerCase()}` : "No changes noticed";
  const head = `${raised} change${raised === 1 ? "" : "s"} noticed`;
  if (!closed) return head;
  return closed >= raised ? `${head}, all followed up` : `${head}, ${closed} followed up so far`;
}

/** "This week for Lakshmi"; "This week for you" when Lakshmi is reading. */
export function weekTitle(name: string | null | undefined, isSelf = false): string {
  return `This week for ${isSelf ? "you" : (name || "").trim() || "your family member"}`;
}

function share(label: string, s: WeekShare) {
  if (!s.answered) return null;
  const arrow = s.trend === "better" ? " ↑" : s.trend === "worse" ? " ↓" : "";
  return (
    <li>
      <strong>{label}</strong> as usual on {s.good} of {s.answered}
      {s.prev_answered ? <span className="muted"> (last week {s.prev_good} of {s.prev_answered}){arrow}</span> : null}
    </li>
  );
}

/** "This week for Amma": refreshed each Monday (IST) from last week's KushLife visits. */
export function KushLifeWeekCard({
  changesNoted,
  isSelf = false,
}: { changesNoted?: string[] | null; isSelf?: boolean } = {}) {
  const [w, setW] = useState<Week | null>(null);
  const [more, setMore] = useState(false);
  const tz = useFamilyTimezone();
  useEffect(() => {
    familyApi<Week>("/kushlife/week").then(setW).catch(() => undefined);
  }, []);
  if (!w || (!w.card.visits_done && !w.summary)) return null;
  const c = w.card;
  const v = c.vitals;
  const p = c.vitals_prev;
  const b = c.baseline;
  return (
    <section className="card home-safety-section fh-kl-week" aria-label={weekTitle(c.name, isSelf)}>
      <h2>{weekTitle(c.name, isSelf)}</h2>
      <p className="muted">
        {day(c.week_start)} – {day(c.week_end)} · {c.visits_done} visit{c.visits_done === 1 ? "" : "s"}
        {c.visits_prev !== c.visits_done ? ` (${c.visits_prev} the week before)` : ""}
      </p>
      {w.summary ? <p className="fh-kl-week-summary">{w.summary.text}</p> : null}
      {w.summary ? (
        <button type="button" className="fh-kl-week-more" aria-expanded={more} onClick={() => setMore((m) => !m)}>
          {more ? "Hide details" : "Details"}
        </button>
      ) : null}
      {!w.summary || more ? (
      <ul className="fh-kl-week-list">
        {share("Mood", c.trend.mood)}
        {share("Sleep", c.trend.sleep)}
        {share("Appetite", c.trend.appetite)}
        {v.bp_sys && v.bp_dia ? (
          <li>
            <strong>BP</strong> around {v.bp_sys}/{v.bp_dia}
            {p.bp_sys && p.bp_dia ? <span className="muted"> (last week {p.bp_sys}/{p.bp_dia})</span> : null}
            {b.bp_sys && b.bp_dia ? <span className="muted"> · Normal for {c.name}: {b.bp_sys}/{b.bp_dia}</span> : null}
          </li>
        ) : null}
        {v.spo2 ? (
          <li>
            <strong>Oxygen</strong> around {v.spo2}%
            {p.spo2 ? <span className="muted"> (last week {p.spo2}%)</span> : null}
            {b.spo2 ? <span className="muted"> · Normal for {c.name}: {b.spo2}%</span> : null}
          </li>
        ) : null}
        <li>{changesLine(c.flags.raised, c.flags.closed, changesNoted ?? [])}</li>
        {c.next_visits.length ? (
          <li>
            <strong>Next visit</strong> {formatInZone(c.next_visits[0].date, tz)}
          </li>
        ) : null}
      </ul>
      ) : null}
    </section>
  );
}
