"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatIST } from "@/lib/ist";
import { VitalsTrend } from "@/components/kushlife/VitalsTrend";
import { VoicePlayer } from "@/components/kushlife/VoicePlayer";
import {
  fmtPct,
  openPdf,
  type AgencyQuality,
  type FeedbackRow,
  type MonthlyLetter,
  type MonthlyPending,
  type NpsSummary,
  type QualityNumbers,
  type VitalsSeries,
  type VoiceNote,
} from "@/lib/kushlife-quality";
import "@/components/kushlife/vitals-trend.css";
import { can } from "@/lib/roles";

function Tiles({ q, nps }: { q: QualityNumbers; nps?: NpsSummary }) {
  return (
    <div className="kq-tiles">
      <div className="kq-tile"><strong>{fmtPct(q.on_time_pct)}</strong><span>Visits on time ({q.on_time_measured} timed)</span></div>
      <div className="kq-tile"><strong>{fmtPct(q.kushlife_pct)}</strong><span>Visits with KushLife ({q.visits_done})</span></div>
      <div className="kq-tile"><strong>{q.avg_rating ?? "—"}</strong><span>Family rating ({q.ratings})</span></div>
      <div className="kq-tile"><strong>{q.incidents}</strong><span>Incidents</span></div>
      {nps ? <div className="kq-tile"><strong>{nps.nps ?? "—"}</strong><span>Family recommend score ({nps.responses === 1 ? "1 answer" : `${nps.responses} answers`})</span></div> : null}
    </div>
  );
}

function Letters({ elderId }: { elderId: number }) {
  const base = `/api/v1/home-safety/clients/${elderId}/kushlife/monthly`;
  const [rows, setRows] = useState<MonthlyLetter[] | null>(null);
  const [form, setForm] = useState<Record<number, { text: string; manager_note: string; next_plan: string }>>({});
  const [busy, setBusy] = useState(0);
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    api<{ letters: MonthlyLetter[] }>(base)
      .then((r) => {
        setRows(r.letters);
        setForm(Object.fromEntries(r.letters.map((l) => [l.id, { text: l.text, manager_note: l.manager_note, next_plan: l.next_plan }])));
      })
      .catch(() => undefined);
  }, [base]);
  useEffect(() => load(), [load]);
  useEffect(() => {
    if (rows && window.location.hash === "#kushlife-monthly") document.getElementById("kushlife-monthly")?.scrollIntoView({ block: "start" });
  }, [rows]);

  async function act(id: number, approve: boolean) {
    setBusy(id);
    setErr("");
    try {
      await api(approve ? `${base}/${id}/approve` : `${base}/${id}`, { method: approve ? "POST" : "PUT", body: JSON.stringify(form[id]) });
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(0);
    }
  }

  if (!rows || !rows.length) return null;
  const set = (id: number, k: "text" | "manager_note" | "next_plan", v: string) => setForm({ ...form, [id]: { ...form[id], [k]: v } });
  return (
    <div id="kushlife-monthly">
      <h3>Monthly KushLife letters</h3>
      <p className="kq-muted">Drafted on the 1st for last month. The family sees a letter (page and PDF) only after you approve it.</p>
      {err ? <p role="alert">{err}</p> : null}
      {rows.map((l) => (
        <div key={l.id} className="kq-row">
          <div className="kq-actions">
            <strong>{l.month_label}</strong>
            <span className={`kq-status ${l.status === "draft" ? (l.overdue ? "is-red" : "is-amber") : ""}`}>
              {l.status === "approved" ? "Sent to family" : l.overdue ? "Waiting — overdue" : "Draft"}
            </span>
            <button type="button" className="secondary" onClick={() => void openPdf(`${base}/${l.id}/pdf`).catch((e) => setErr(e.message))}>
              PDF
            </button>
          </div>
          {l.status === "draft" && can("edit") ? (
            <>
              <label>Letter<textarea rows={6} value={form[l.id]?.text ?? ""} onChange={(e) => set(l.id, "text", e.target.value)} /></label>
              <label>Your note to the family<textarea rows={2} value={form[l.id]?.manager_note ?? ""} onChange={(e) => set(l.id, "manager_note", e.target.value)} /></label>
              <label>Next month&apos;s plan<textarea rows={2} value={form[l.id]?.next_plan ?? ""} onChange={(e) => set(l.id, "next_plan", e.target.value)} /></label>
              <div className="kq-actions">
                <button type="button" className="secondary" disabled={busy === l.id} onClick={() => void act(l.id, false)}>Save</button>
                <button type="button" className="btn btn-primary" disabled={busy === l.id || !(form[l.id]?.text ?? "").trim()} onClick={() => void act(l.id, true)}>
                  Approve and send
                </button>
              </div>
            </>
          ) : (
            <p className="kq-muted" style={{ whiteSpace: "pre-wrap" }}>{l.text}</p>
          )}
        </div>
      ))}
    </div>
  );
}

function VoiceNotes({ elderId }: { elderId: number }) {
  const [rows, setRows] = useState<VoiceNote[] | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(() => {
    api<VoiceNote[]>(`/api/v1/home-safety/clients/${elderId}/voice-notes`).then(setRows).catch(() => undefined);
  }, [elderId]);
  useEffect(() => load(), [load]);
  if (!rows || !rows.length) return null;
  async function share(n: VoiceNote, on: boolean) {
    setErr("");
    try {
      await api(`/api/v1/home-safety/voice-notes/${n.id}/share`, { method: "POST", body: JSON.stringify({ share: on }) });
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save");
    }
  }
  return (
    <div>
      <h3>Voice notes from visits</h3>
      <p className="kq-muted">The family hears a note only when you tick &ldquo;Share with family&rdquo;.</p>
      {err ? <p role="alert">{err}</p> : null}
      {rows.map((n) => (
        <div key={n.id} className="kq-row kq-voice">
          <span>{n.created_at ? formatIST(n.created_at) : ""}{n.recorded_by_name ? ` · ${n.recorded_by_name}` : ""}</span>
          <VoicePlayer note={n} />
          <label className="kq-actions">
            <input type="checkbox" checked={!!n.share_with_family} onChange={(e) => void share(n, e.target.checked)} />
            Share with family
          </label>
        </div>
      ))}
    </div>
  );
}

/** Ops client page: quality numbers, vitals trend, monthly letters, voice notes, family ratings. */
export function KushLifeQualityPanel({ elderId }: { elderId: number }) {
  const [q, setQ] = useState<(QualityNumbers & { nps: NpsSummary }) | null>(null);
  const [vitals, setVitals] = useState<VitalsSeries | null>(null);
  const [fb, setFb] = useState<{ ratings: { id: number; rating: number; comment: string; by_name: string; created_at: string | null }[] } | null>(null);
  useEffect(() => {
    api<QualityNumbers & { nps: NpsSummary }>(`/api/v1/home-safety/clients/${elderId}/quality?days=90`).then(setQ).catch(() => undefined);
    api<VitalsSeries>(`/api/v1/home-safety/clients/${elderId}/kushlife/vitals`).then(setVitals).catch(() => undefined);
    api<typeof fb>(`/api/v1/home-safety/clients/${elderId}/feedback`).then(setFb).catch(() => undefined);
  }, [elderId]);
  return (
    <div className="kq">
      {q ? (
        <div>
          <h3>Quality — last 90 days</h3>
          <Tiles q={q} nps={q.nps} />
        </div>
      ) : null}
      <VitalsTrend data={vitals} />
      <Letters elderId={elderId} />
      <VoiceNotes elderId={elderId} />
      {fb?.ratings.length ? (
        <div>
          <h3>Family ratings</h3>
          {fb.ratings.slice(0, 8).map((r) => (
            <p key={r.id} className="kq-muted">
              {"★".repeat(r.rating)}{"☆".repeat(5 - r.rating)} · {r.by_name}
              {r.created_at ? ` · ${formatIST(r.created_at, { dateOnly: true })}` : ""}
              {r.comment ? ` — “${r.comment}”` : ""}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

// --- Dashboard ----------------------------------------------------------------------------

export function useMonthlyPending(): MonthlyPending | null {
  const [data, setData] = useState<MonthlyPending | null>(null);
  useEffect(() => {
    api<MonthlyPending>("/api/v1/home-safety/quality/monthly-pending").then(setData).catch(() => undefined);
  }, []);
  return data;
}

/** Needs-attention rows: monthly letters waiting for approval (overdue after the 5th, 6 PM). */
export function MonthlyLetterRows({ data }: { data: MonthlyPending | null }) {
  if (!data?.items.length) return null;
  return (
    <>
      {data.items.map((i) => {
        const href = `/kushalaya/customers/${i.elder_id}#kushlife-monthly`;
        return (
          <li key={`km${i.id}`} className="has-actions dash-two-line">
            <a href={href}>
              <span className={`dash-tag ${i.overdue ? "is-red" : "is-gold"}`}>Monthly letter</span>
              <strong>{i.elder_name}</strong>
              <span>{i.month_label} · waiting for your approval</span>
              <small>{i.overdue ? "Overdue (due the 5th, 6 PM)" : "Due the 5th, 6 PM"}</small>
            </a>
            <a href={href} className="dash-act">Open</a>
          </li>
        );
      })}
    </>
  );
}

/** Needs-attention rows: visit ratings ≤ 2 and NPS detractors, until marked reviewed. */
export function FeedbackRows({ rows, busy, onReviewed }: { rows: FeedbackRow[] | undefined; busy: string; onReviewed?: (key: string, url: string) => void }) {
  if (!rows?.length) return null;
  return (
    <>
      {rows.map((f) => {
        const key = `fb${f.kind}${f.id}`;
        return (
          <li key={key} className="has-actions dash-two-line">
            <a href={`/kushalaya/customers/${f.elder_id}`}>
              <span className="dash-tag is-red">{f.kind === "rating" ? `Rated ${f.score}/5` : `Would recommend ${f.score}/10`}</span>
              <strong>{f.elder_name}</strong>
              <span>
                {f.by_name}
                {f.comment ? ` · “${f.comment.length > 80 ? `${f.comment.slice(0, 77)}…` : f.comment}”` : ""}
              </span>
              <small>{f.kind === "rating" ? "Low visit rating" : "Unlikely to recommend"}</small>
            </a>
            {onReviewed ? (
              <button type="button" className="dash-act" disabled={busy === key}
                onClick={() => onReviewed(key, `/api/v1/home-safety/feedback/${f.kind}/${f.id}/review`)}>
                Reviewed
              </button>
            ) : null}
          </li>
        );
      })}
    </>
  );
}

/** Dashboard card: agency quality numbers and NPS (my team for care managers). */
export function AgencyQualityCard() {
  const [d, setD] = useState<AgencyQuality | null>(null);
  useEffect(() => {
    api<AgencyQuality>("/api/v1/home-safety/quality?days=30").then(setD).catch(() => undefined);
  }, []);
  if (!d) return null;
  return (
    <section className="kq" aria-labelledby="kq-agency-h">
      <h2 id="kq-agency-h">Care quality — last 30 days</h2>
      <Tiles q={d.agency} nps={d.nps} />
      {d.clients.length ? (
        <details className="vt-table">
          <summary>Per client</summary>
          <table>
            <thead><tr><th>Client</th><th>On time</th><th>KushLife</th><th>Rating</th><th>Incidents</th></tr></thead>
            <tbody>
              {d.clients.map((c) => (
                <tr key={c.elder_id}>
                  <td><a href={`/kushalaya/customers/${c.elder_id}`}>{c.elder_name}</a></td>
                  <td>{fmtPct(c.on_time_pct)}</td>
                  <td>{fmtPct(c.kushlife_pct)}</td>
                  <td>{c.avg_rating ?? "—"}</td>
                  <td>{c.incidents}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      ) : null}
    </section>
  );
}
