"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { OpsModal } from "@/components/ops/OpsModal";
import { api } from "@/lib/api";
import { canManageUsers } from "@/lib/auth";
import { getStoredAuth } from "@/lib/api";

type Kpi = {
  key: string;
  label: string;
  unit: "count" | "paise";
  target: number | null;
  achieved: number;
  percent: number | null;
};
type Person = { user_id: number; name: string; kpis: Kpi[] };
type Report = { month: string; as_of: string | null; month_start: string; people: Person[] };

function money(paise: number): string {
  return `₹${Math.round(paise / 100).toLocaleString("en-IN")}`;
}

function value(k: Kpi, v: number | null): string {
  if (v == null) return "—";
  return k.unit === "paise" ? money(v) : String(v);
}

function monthName(month: string): string {
  const d = new Date(`${month}-01T00:00:00Z`);
  return new Intl.DateTimeFormat("en-IN", { month: "long", year: "numeric", timeZone: "UTC" }).format(d);
}

/** Dashboard: each person's KPIs against their monthly target, month to date. */
export function TeamTargets() {
  const isAdmin = canManageUsers(getStoredAuth()?.role || "");
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<Person | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    api<Report>("/api/v1/sales/targets")
      .then((r) => {
        setReport(r);
        setError("");
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load targets"));
  }, []);

  useEffect(load, [load]);

  function openEdit(p: Person) {
    setEditing(p);
    setDraft(
      Object.fromEntries(
        p.kpis.map((k) => [k.key, k.target == null ? "" : String(k.unit === "paise" ? Math.round(k.target / 100) : k.target)]),
      ),
    );
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!editing || !report) return;
    setSaving(true);
    try {
      const targets = Object.fromEntries(
        editing.kpis.map((k) => {
          const raw = (draft[k.key] || "").replace(/[₹,\s]/g, "");
          if (!raw) return [k.key, null];
          const n = Math.max(0, Math.round(Number(raw)));
          return [k.key, k.unit === "paise" ? n * 100 : n];
        }),
      );
      setReport(
        await api<Report>("/api/v1/sales/targets", {
          method: "PUT",
          body: JSON.stringify({ month: report.month, user_id: editing.user_id, targets }),
        }),
      );
      setEditing(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setSaving(false);
    }
  }

  if (!report && !error) return null;
  const people = report?.people ?? [];
  const cols = people[0]?.kpis ?? [];

  return (
    <section className="card tt" aria-labelledby="tt-title">
      <header className="tt-head">
        <h2 id="tt-title">{report ? monthName(report.month) : ""}</h2>
        {report?.as_of ? <span className="muted">Done / target, month to date</span> : null}
      </header>
      {error ? (
        <p className="error" role="alert">
          {error}
        </p>
      ) : null}
      {report && people.length === 0 ? <p className="muted">No team members yet.</p> : null}
      {people.length ? (
        <div className="tt-scroll">
          <table className="tt-table tt-grid">
            <thead>
              <tr>
                <th scope="col">Team member</th>
                {cols.map((k) => (
                  <th key={k.key} scope="col">
                    {k.label}
                  </th>
                ))}
                {isAdmin ? <th scope="col" aria-label="Actions" /> : null}
              </tr>
            </thead>
            <tbody>
              {people.map((p) => (
                <tr key={p.user_id}>
                  <th scope="row" className="tt-who">
                    {p.name}
                  </th>
                  {p.kpis.map((k) => (
                    <td key={k.key}>
                      <span className="tt-val">
                        <strong>{value(k, k.achieved)}</strong>
                        <span className="muted"> / {value(k, k.target)}</span>
                      </span>
                      {k.percent == null ? null : (
                        <span className={`tt-pct ${k.percent >= 100 ? "is-done" : k.percent >= 50 ? "is-mid" : "is-low"}`}>
                          {k.percent}%
                        </span>
                      )}
                    </td>
                  ))}
                  {isAdmin ? (
                    <td>
                      {p.user_id !== 0 ? (
                        <button type="button" className="secondary tt-set" onClick={() => openEdit(p)}>
                          Set targets
                        </button>
                      ) : null}
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <OpsModal open={editing !== null} title={editing ? `Targets for ${editing.name}` : ""} onClose={() => setEditing(null)}>
        {editing ? (
          <form onSubmit={save} className="tt-form">
            <p className="muted">For {report ? monthName(report.month) : ""}. They carry forward to next month until changed.</p>
            {editing.kpis.map((k) => (
              <label key={k.key}>
                {k.label}
                {k.unit === "paise" ? " (₹)" : ""}
                <input
                  inputMode="numeric"
                  value={draft[k.key] ?? ""}
                  onChange={(e) => setDraft({ ...draft, [k.key]: e.target.value })}
                  placeholder="No target"
                />
              </label>
            ))}
            <div className="tt-actions">
              <button type="button" className="secondary" onClick={() => setEditing(null)} disabled={saving}>
                Cancel
              </button>
              <button type="submit" disabled={saving}>
                {saving ? "Saving…" : "Save targets"}
              </button>
            </div>
          </form>
        ) : null}
      </OpsModal>
    </section>
  );
}
