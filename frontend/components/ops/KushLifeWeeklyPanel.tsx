"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { weekRange } from "@/lib/ist";
import type { BaselineKey, KushLifeBaseline, KushLifeWeekly } from "@/lib/kushlife";
import "../kushlife.css";
import { can } from "@/lib/roles";

const NUM: { key: BaselineKey; label: string }[] = [
  { key: "bp_sys", label: "BP top" },
  { key: "bp_dia", label: "BP bottom" },
  { key: "spo2", label: "Oxygen %" },
  { key: "pulse", label: "Pulse" },
];
const CAT: { key: BaselineKey; label: string; options: Record<string, string> }[] = [
  { key: "sleep", label: "Sleep", options: { well: "Sleeps well", poorly: "Sleeps poorly" } },
  { key: "appetite", label: "Appetite", options: { usual: "Eats as usual", less: "Eats less", more: "Eats more" } },
  { key: "mood", label: "Mood", options: { good: "Good mood", low: "Low mood" } },
];

/** "Normal for Amma": computed from the last visits; staff can override any item (blank = computed). */
export function KushLifeBaselineEditor({ elderId, onSaved }: { elderId: number; onSaved?: () => void }) {
  const url = `/api/v1/home-safety/clients/${elderId}/kushlife/baseline`;
  const [b, setB] = useState<KushLifeBaseline | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [open, setOpen] = useState(false);
  const [msg, setMsg] = useState("");

  const load = useCallback(() => {
    api<KushLifeBaseline>(url)
      .then((r) => {
        setB(r);
        const f: Record<string, string> = {};
        for (const k of [...NUM, ...CAT]) f[k.key] = r.source[k.key] === "override" ? String(r.values[k.key] ?? "") : "";
        setForm(f);
      })
      .catch(() => undefined);
  }, [url]);
  useEffect(() => load(), [load]);

  async function save() {
    setMsg("");
    const body: Record<string, string | number | null> = {};
    for (const k of NUM) body[k.key] = form[k.key] ? Number(form[k.key]) : null;
    for (const k of CAT) body[k.key] = form[k.key] || null;
    try {
      const r = await api<KushLifeBaseline>(url, { method: "PUT", body: JSON.stringify(body) });
      setB(r);
      setMsg("Saved");
      onSaved?.();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Could not save");
    }
  }

  if (!b) return null;
  const shown = (k: BaselineKey) => (b.computed[k] != null ? String(b.computed[k]) : "none yet");
  return (
    <div className="kl-baseline">
      <button type="button" className="kl-link" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {open ? "Hide" : `${b.label} — edit`}
      </button>
      {open ? (
        <div>
          <p className="kl-muted">
            Worked out from the last {b.visits_used} visits (unusual readings left out). Type a value to set it
            yourself, or leave the box blank to keep using the visits. Each visit is compared with these values.
            {b.override_by ? ` Last changed by ${b.override_by}.` : ""}
          </p>
          <div className="kl-vitals kl-normal-grid">
            {NUM.map((k) => (
              <label key={k.key}>
                {k.label}
                <input inputMode="numeric" value={form[k.key] ?? ""} placeholder={shown(k.key)}
                  onChange={(e) => setForm({ ...form, [k.key]: e.target.value.replace(/[^0-9]/g, "") })} />
              </label>
            ))}
            {CAT.map((k) => (
              <label key={k.key}>
                {k.label}
                <select value={form[k.key] ?? ""} onChange={(e) => setForm({ ...form, [k.key]: e.target.value })}>
                  <option value="">
                    Auto ({b.computed[k.key] != null ? (k.options[String(b.computed[k.key])] ?? String(b.computed[k.key])) : "none yet"})
                  </option>
                  {Object.entries(k.options).map(([v, l]) => (
                    <option key={v} value={v}>{l}</option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          <button type="button" className="secondary" onClick={() => void save()}>Save normal values</button>
          {msg ? <span className="kl-muted"> {msg}</span> : null}
        </div>
      ) : null}
    </div>
  );
}

/** Weekly summaries for one client: the care manager edits the draft and approves it for the family. */
export function KushLifeWeeklyPanel({ elderId }: { elderId: number }) {
  const base = `/api/v1/home-safety/clients/${elderId}/kushlife/weekly`;
  const [rows, setRows] = useState<KushLifeWeekly[] | null>(null);
  const [text, setText] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(0);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    api<{ summaries: KushLifeWeekly[] }>(base)
      .then((r) => {
        setRows(r.summaries);
        setText(Object.fromEntries(r.summaries.map((s) => [s.id, s.text])));
      })
      .catch(() => undefined);
  }, [base]);
  useEffect(() => load(), [load]);
  // Arriving from the dashboard ("#kushlife-weekly"): scroll once the summaries have loaded.
  const loaded = rows !== null;
  useEffect(() => {
    if (loaded && window.location.hash === "#kushlife-weekly") {
      document.getElementById("kushlife-weekly")?.scrollIntoView({ block: "start" });
    }
  }, [loaded]);

  async function act(id: number, approve: boolean) {
    setBusy(id);
    setErr("");
    try {
      await api(approve ? `${base}/${id}/approve` : `${base}/${id}`, {
        method: approve ? "POST" : "PUT",
        body: JSON.stringify({ text: text[id] }),
      });
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(0);
    }
  }

  if (!rows || !rows.length) return null;
  return (
    <div className="kl-weekly" id="kushlife-weekly">
      <h3>Weekly summaries</h3>
      <p className="kl-muted">Drafted every Monday morning. The family sees a summary only after you approve it.</p>
      {err ? <p role="alert">{err}</p> : null}
      {rows.map((s) => (
        <div key={s.id} className="kl-weekly-row">
          <strong>{weekRange(s.week_start)}</strong>{" "}
          <span className={`kl-status ${s.status === "draft" ? (s.overdue ? "is-red" : "is-amber") : ""}`}>
            {s.status === "approved" ? "Sent to family" : s.overdue ? "Waiting — overdue" : "Draft"}
          </span>
          {s.status === "draft" && can("edit") ? (
            <>
              <textarea rows={4} value={text[s.id] ?? ""} onChange={(e) => setText({ ...text, [s.id]: e.target.value })} />
              <button type="button" className="secondary" disabled={busy === s.id} onClick={() => void act(s.id, false)}>
                Save
              </button>{" "}
              <button type="button" className="btn btn-primary" disabled={busy === s.id || !(text[s.id] ?? "").trim()} onClick={() => void act(s.id, true)}>
                Approve and send
              </button>
            </>
          ) : (
            <p>{s.text}</p>
          )}
        </div>
      ))}
    </div>
  );
}

export type KushLifeWeeklyPending = {
  items: { id: number; elder_id: number; elder_name: string; week_start: string; overdue: boolean }[];
  overdue: number;
};

/** Dashboard: summaries still waiting for approval (overdue after Tuesday 18:00 IST). */
export function useKushLifeWeeklyPending(): KushLifeWeeklyPending | null {
  const [data, setData] = useState<KushLifeWeeklyPending | null>(null);
  useEffect(() => {
    api<KushLifeWeeklyPending>("/api/v1/home-safety/clients/kushlife-weekly/pending").then(setData).catch(() => undefined);
  }, []);
  return data;
}

/** "1 is overdue (due Tuesday 6 PM)" — empty when nothing is overdue. */
export function weeklyOverdueLine(data: KushLifeWeeklyPending | null): string {
  if (!data?.overdue) return "";
  return `${data.overdue} weekly summar${data.overdue === 1 ? "y is" : "ies are"} overdue (due Tuesday 6 PM)`;
}

/** Needs-attention rows (dashboard): one per summary waiting for approval. */
export function KushLifeWeeklyRows({ data }: { data: KushLifeWeeklyPending | null }) {
  if (!data?.items.length) return null;
  return (
    <>
      {data.items.map((i) => {
        const href = `/kushalaya/customers/${i.elder_id}#kushlife-weekly`;
        return (
          <li key={`kw${i.id}`} className="has-actions">
            <a href={href}>
              <span className={`dash-tag ${i.overdue ? "is-red" : "is-gold"}`}>Weekly summary</span>
              <strong>{i.elder_name}</strong>
              <span>{weekRange(i.week_start)} · waiting for your approval</span>
              <small>{i.overdue ? "Overdue (due Tuesday 6 PM)" : "Due Tuesday 6 PM"}</small>
            </a>
            <a href={href} className="dash-act">
              Open
            </a>
          </li>
        );
      })}
    </>
  );
}
