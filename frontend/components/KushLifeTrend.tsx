"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { formatIST } from "@/lib/ist";
import { normalLine, type KushLifeView } from "@/lib/kushlife";
import { KushLifeLifeline } from "@/components/kushlife/KushLifeLifeline";
import "./kushlife.css";

const SLEEP = { well: "Slept well", poorly: "Slept poorly", unsure: "Sleep not known" } as Record<string, string>;
const APPETITE = { usual: "Ate as usual", less: "Ate less", more: "Ate more" } as Record<string, string>;

function shortDate(iso: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" });
}

function shortTime(iso: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", timeZone: "Asia/Kolkata" });
}

/**
 * KushLife trend: four rows (Safe / Steady / Settled / Connected) × recent visits as dots,
 * one plain sentence, the latest visit, and (for staff) open flags to acknowledge.
 */
function readings(v: Record<string, number>): string {
  return [
    v.bp_sys && v.bp_dia ? `BP ${v.bp_sys}/${v.bp_dia}` : "",
    v.spo2 ? `Oxygen ${v.spo2}%` : "",
    v.pulse ? `Pulse ${v.pulse}` : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

export function KushLifeTrend({
  view,
  staff = false,
  ackUrl,
  onChanged,
  title = "KushLife",
  lifeline = true,
}: {
  view: KushLifeView;
  staff?: boolean;
  ackUrl?: string;
  onChanged?: () => void;
  title?: string;
  /** Draw the lifeline chart on top (off where the page shows it separately). */
  lifeline?: boolean;
}) {
  const [why, setWhy] = useState(false);
  const [busy, setBusy] = useState("");
  const visits = [...view.visits].reverse(); // oldest → newest, left → right
  const cols = Math.max(visits.length, 1);
  const tone = view.status === "We're calling you" ? "is-red" : view.status === "Watching closely" ? "is-amber" : "";
  const last = view.visits[0];
  // Two visits on the same day: show the time too, so columns can be told apart.
  const dates = visits.map((v) => shortDate(v.date));
  const repeated = (i: number) => dates.filter((d) => d === dates[i]).length > 1;
  // Header: the date once per day; later visits that day show only the time.
  const colLabel = (i: number) =>
    !repeated(i)
      ? dates[i]
      : dates.indexOf(dates[i]) === i
        ? `${dates[i]} ${shortTime(visits[i].date)}`
        : shortTime(visits[i].date);
  // Screen readers always get the full date (and time when needed).
  const fullLabel = (i: number) =>
    repeated(i) ? `${dates[i]} ${shortTime(visits[i].date)}` : dates[i];

  async function ack(key: string) {
    if (!ackUrl) return;
    setBusy(key);
    try {
      await api(ackUrl, { method: "POST", body: JSON.stringify({ key }) });
      onChanged?.();
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="kl-trend">
      <div className="kl-trend-head">
        <h2>{title}</h2>
        <span className={`kl-status ${tone}`}>{view.status}</span>
      </div>
      <p className="kl-sentence">{view.summary_line}</p>
      {lifeline ? <KushLifeLifeline view={view} /> : null}
      {view.pct_ok_30d != null && visits.length ? (
        <p className="kl-pct">{view.pct_ok_30d}% of checks as usual in the last 30 days</p>
      ) : null}

      {visits.length ? (
        <div className="kl-grid" style={{ ["--kl-cols" as string]: cols }}>
          <span />
          {visits.map((v, i) => (
            <span key={`d${v.job_id}`} className="kl-grid-date" aria-hidden="true">
              {colLabel(i)}
            </span>
          ))}
          {view.checks.map((c) => (
            <Row
              key={c.key}
              label={c.label}
              cells={visits.map((v) => v.checks[c.key])}
              ids={visits.map((v) => v.job_id)}
              dates={visits.map((_, i) => fullLabel(i))}
            />
          ))}
        </div>
      ) : null}
      {visits.length ? (
        <p className="kl-legend">
          <span>As usual</span>
          <span className="is-concern">Changed</span>
        </p>
      ) : null}

      {last ? (
        <div className="kl-last">
          <strong>Last visit · {formatIST(last.date)}</strong>
          <p>
            {[SLEEP[last.sleep ?? ""], APPETITE[last.appetite ?? ""]].filter(Boolean).join(" · ")}
            {Object.values(last.chips).flat().length ? ` · Changed: ${Object.values(last.chips).flat().join(", ").toLowerCase()}` : ""}
          </p>
          {last.note ? <p>“{last.note}”</p> : null}
          {readings(last.vitals) ? (
            <>
              <p className="kl-readings">{readings(last.vitals)}</p>
              {normalLine(view.baseline, last.vitals) ? (
                <p className="kl-muted kl-normal">{normalLine(view.baseline, last.vitals)}</p>
              ) : null}
            </>
          ) : null}
        </div>
      ) : null}

      {staff && view.flags.length ? (
        <ul className="kl-flags">
          {view.flags.map((f) => (
            <li key={f.key} className={f.level === "red" ? "is-red" : ""}>
              <span>
                <strong>{f.level === "red" ? "Red" : "Amber"}:</strong> {f.reason}
                <br />
                <small>
                  {f.acknowledged_by ? `Seen by ${f.acknowledged_by}` : f.level === "red" ? "Call the family within 2 hours" : "Look at it within 24 hours"}
                </small>
              </span>
              {!f.acknowledged_at && ackUrl ? (
                <button type="button" className="kl-link" disabled={busy === f.key} onClick={() => void ack(f.key)}>
                  {busy === f.key ? "Saving…" : "I've seen it"}
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      <button
        type="button"
        className="kl-link"
        onClick={() => setWhy((w) => !w)}
        aria-expanded={why}
        aria-label={why ? "Hide what KushLife is" : "What is KushLife?"}
      >
        {why ? "Hide" : "What is KushLife?"}
      </button>
      {why ? <p className="kl-muted">{view.explain}</p> : null}
    </div>
  );
}

function Row({ label, cells, ids, dates }: { label: string; cells: ("ok" | "concern")[]; ids: number[]; dates: string[] }) {
  return (
    <>
      <span
        className="kl-grid-label"
        aria-label={`${label}: as usual on ${cells.filter((c) => c === "ok").length} of ${cells.length} visits`}
      >
        {label}
      </span>
      {cells.map((s, i) => (
        <span
          key={`${label}${ids[i]}`}
          role="img"
          aria-label={`${label}, ${dates[i]}: ${s === "concern" ? "changed" : "as usual"}`}
          className={`kl-dot${s === "concern" ? " is-concern" : ""}`}
          title={s === "concern" ? "Changed" : "As usual"}
        />
      ))}
    </>
  );
}
