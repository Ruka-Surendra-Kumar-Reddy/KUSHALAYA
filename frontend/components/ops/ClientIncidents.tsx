"use client";

import { useCallback, useEffect, useState } from "react";
import { formatIST } from "@/lib/ist";
import {
  closeIncident,
  createIncident,
  INCIDENT_KINDS,
  isSerious,
  listIncidents,
  localToIso,
  reviewIncident,
  updateIncident,
  type FollowUp,
  type IncidentCounts,
  type IncidentReport,
} from "@/lib/incident-reports";
import "./incidents.css";
import { OpsModal } from "./OpsModal";
import { can } from "@/lib/roles";

const EMPTY = {
  kind: "",
  what_happened: "",
  occurred_at: "",
  location: "",
  injury: "",
  action_taken: "",
  witnesses: "",
  family_informed: false,
  family_informed_at: "",
  serious: false,
};

/** sessionStorage key: an emergency closed as a hospital admission leaves a pre-filled report here. */
export const INCIDENT_PREFILL_KEY = "ks-incident-prefill";

/** Client page → Incidents (#97): falls, near-misses, medication errors, complaints, with follow-up. */
export function ClientIncidents({ elderId }: { elderId: number }) {
  const [rows, setRows] = useState<IncidentReport[] | null>(null);
  const [counts, setCounts] = useState<IncidentCounts | null>(null);
  const [form, setForm] = useState<typeof EMPTY | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () =>
      listIncidents(elderId)
        .then((r) => {
          setRows(r.reports);
          setCounts(r.counts ?? null);
        })
        .catch((e) => setError(e instanceof Error ? e.message : "Could not load reports")),
    [elderId],
  );
  useEffect(() => {
    void load();
  }, [load]);

  // Opened from Alerts after "Admitted to hospital": start the report already filled in.
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(INCIDENT_PREFILL_KEY);
      if (!raw) return;
      const pre = JSON.parse(raw) as Partial<typeof EMPTY> & { elder_id?: number };
      if (pre.elder_id !== elderId) return;
      sessionStorage.removeItem(INCIDENT_PREFILL_KEY);
      const { elder_id: _ignored, ...fields } = pre;
      void _ignored;
      setForm({ ...EMPTY, ...fields });
    } catch {
      /* storage blocked: the manager can still press "+ New report" */
    }
  }, [elderId]);

  async function file() {
    if (!form) return;
    if (!form.kind || !form.what_happened.trim()) {
      setError("Pick the kind and say what happened.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await createIncident({
        ...form,
        elder_id: elderId,
        occurred_at: localToIso(form.occurred_at),
        family_informed_at: form.family_informed ? localToIso(form.family_informed_at) : null,
      });
      setForm(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  const set = (patch: Partial<typeof EMPTY>) => setForm((f) => (f ? { ...f, ...patch } : f));

  return (
    <section className="card ir">
      <div className="ir-head">
        <h2>Incident reports</h2>
        {counts ? (
          <span className="muted">
            {counts.total} report{counts.total === 1 ? "" : "s"} · {counts.falls} fall{counts.falls === 1 ? "" : "s"} (
            {counts.falls_90d} in 90 days) · {counts.open} waiting for review
          </span>
        ) : null}
        {form || !can("edit") ? null : (
          <button type="button" onClick={() => setForm({ ...EMPTY })}>
            + New report
          </button>
        )}
      </div>
      <p className="muted">For things that already happened. Live SOS and band alerts are under SOS &amp; alerts.</p>

      <OpsModal open={!!form} title="New incident report" onClose={() => setForm(null)} wide>
      {form ? (
        <div className="ir-form">
          <label>
            What kind
            <select value={form.kind} onChange={(e) => set({ kind: e.target.value })}>
              <option value="">Choose…</option>
              {INCIDENT_KINDS.map((k) => (
                <option key={k.value} value={k.value}>
                  {k.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            When (IST)
            <input type="datetime-local" value={form.occurred_at} onChange={(e) => set({ occurred_at: e.target.value })} />
          </label>
          <label>
            Where
            <input value={form.location} maxLength={300} onChange={(e) => set({ location: e.target.value })} />
          </label>
          <label className="ir-wide">
            What happened
            <textarea rows={3} value={form.what_happened} maxLength={4000} onChange={(e) => set({ what_happened: e.target.value })} />
          </label>
          <label>
            Injury (empty if none)
            <input value={form.injury} maxLength={2000} onChange={(e) => set({ injury: e.target.value })} />
          </label>
          <label>
            Action taken
            <input value={form.action_taken} maxLength={2000} onChange={(e) => set({ action_taken: e.target.value })} />
          </label>
          <label>
            Witnesses
            <input value={form.witnesses} maxLength={500} onChange={(e) => set({ witnesses: e.target.value })} />
          </label>
          <label className="ir-check">
            <input type="checkbox" checked={form.family_informed} onChange={(e) => set({ family_informed: e.target.checked })} />
            Family informed
          </label>
          {form.family_informed ? (
            <label>
              When the family was told
              <input
                type="datetime-local"
                value={form.family_informed_at}
                onChange={(e) => set({ family_informed_at: e.target.value })}
              />
            </label>
          ) : null}
          <label className="ir-check">
            <input type="checkbox" checked={form.serious} onChange={(e) => set({ serious: e.target.checked })} />
            Mark as serious
          </label>
          {isSerious(form.kind, form.injury, form.serious) ? (
            <p className="ir-warn ir-wide">Serious: the care manager is emailed and it shows in Needs attention until reviewed.</p>
          ) : null}
          <div className="ir-wide ir-row">
            <button type="button" disabled={busy} onClick={() => void file()}>
              {busy ? "Saving…" : "Save report"}
            </button>
            <button type="button" className="secondary" onClick={() => setForm(null)}>
              Cancel
            </button>
          </div>
          {error ? <p className="ir-error ir-wide">{error}</p> : null}
        </div>
      ) : null}
      </OpsModal>
      {error && !form ? <p className="ir-error">{error}</p> : null}

      {rows === null ? (
        <p className="muted">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="muted">No incident reports for this client.</p>
      ) : (
        <ul className="ir-list">
          {rows.map((r) => (
            <IncidentRow key={r.id} report={r} onChanged={load} />
          ))}
        </ul>
      )}
    </section>
  );
}

function IncidentRow({ report, onChanged }: { report: IncidentReport; onChanged: () => void }) {
  const [open, setOpen] = useState(report.status === "open");
  const [notes, setNotes] = useState(report.staff_notes);
  const [summary, setSummary] = useState(report.family_summary);
  const [outcome, setOutcome] = useState(report.outcome);
  const [followUps, setFollowUps] = useState<FollowUp[]>(report.follow_ups);
  const [error, setError] = useState("");
  const closed = report.status === "closed";
  // View-only staff read the report; fields stay locked and the save row is hidden.
  const canEdit = can("edit");
  const locked = closed || !canEdit;

  async function run(fn: () => Promise<unknown>) {
    setError("");
    try {
      await fn();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    }
  }

  const fu = (i: number, patch: Partial<FollowUp>) => setFollowUps(followUps.map((f, j) => (j === i ? { ...f, ...patch } : f)));

  return (
    <li className={`ir-item${report.serious ? " is-serious" : ""}`}>
      <button type="button" className="ir-summary" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <strong>{report.kind_label}</strong>
        {report.serious ? <span className="ir-tag is-serious">Serious</span> : null}
        <span className={`ir-tag is-${report.status}`}>{report.status_label}</span>
        <span className="muted">
          {formatIST(report.occurred_at)}
          {report.location ? ` · ${report.location}` : ""} · by {report.reported_by_name || "staff"}
        </span>
      </button>
      {open ? (
        <div className="ir-body">
          <dl className="ir-facts">
            <dt>What happened</dt>
            <dd>{report.what_happened}</dd>
            {report.injury ? (
              <>
                <dt>Injury</dt>
                <dd>{report.injury}</dd>
              </>
            ) : null}
            {report.action_taken ? (
              <>
                <dt>Action taken</dt>
                <dd>{report.action_taken}</dd>
              </>
            ) : null}
            {report.witnesses ? (
              <>
                <dt>Witnesses</dt>
                <dd>{report.witnesses}</dd>
              </>
            ) : null}
            <dt>Family informed</dt>
            <dd>{report.family_informed ? `Yes${report.family_informed_at ? `, ${formatIST(report.family_informed_at)}` : ""}` : "Not yet"}</dd>
            {closed ? (
              <>
                <dt>Outcome</dt>
                <dd>{report.outcome}</dd>
              </>
            ) : null}
          </dl>

          <h4>Follow-up actions</h4>
          {followUps.length === 0 ? <p className="muted">None yet.</p> : null}
          <ul className="ir-fu">
            {followUps.map((f, i) => (
              <li key={f.id ?? i}>
                <label className="ir-fu-action">
                  <span>Action</span>
                  <input value={f.action} disabled={locked} maxLength={300} onChange={(e) => fu(i, { action: e.target.value })} />
                </label>
                <label>
                  <span>Owner</span>
                  <input value={f.owner} disabled={locked} maxLength={120} onChange={(e) => fu(i, { owner: e.target.value })} />
                </label>
                <label>
                  <span>Due date</span>
                  <input type="date" value={f.due_date ?? ""} disabled={locked} onChange={(e) => fu(i, { due_date: e.target.value || null })} />
                </label>
                <label className="ir-fu-done">
                  <input type="checkbox" checked={f.done} disabled={locked} onChange={(e) => fu(i, { done: e.target.checked })} />
                  <span>Done</span>
                </label>
              </li>
            ))}
          </ul>
          {locked ? null : (
            <button
              type="button"
              className="secondary"
              onClick={() => setFollowUps([...followUps, { action: "", owner: "", due_date: null, done: false }])}
            >
              + Add follow-up
            </button>
          )}

          <label className="ir-block">
            Staff notes (never shown to the family)
            <textarea rows={2} value={notes} maxLength={4000} readOnly={!canEdit} onChange={(e) => setNotes(e.target.value)} />
          </label>
          <label className="ir-block">
            Summary for the family (shown once reviewed; plain words)
            <textarea
              rows={2}
              value={summary}
              disabled={locked}
              maxLength={2000}
              placeholder="Leave empty for a short standard summary"
              onChange={(e) => setSummary(e.target.value)}
            />
          </label>
          {locked ? null : (
            <label className="ir-block">
              Outcome (needed to close)
              <textarea rows={2} value={outcome} maxLength={2000} onChange={(e) => setOutcome(e.target.value)} />
            </label>
          )}
          {error ? <p className="ir-error">{error}</p> : null}
          {canEdit ? (
          <div className="ir-row">
            {closed ? (
              <button type="button" className="secondary" onClick={() => void run(() => updateIncident(report.id, { staff_notes: notes }))}>
                Save notes
              </button>
            ) : (
              <>
                <button
                  type="button"
                  className="secondary"
                  onClick={() =>
                    void run(() => updateIncident(report.id, { staff_notes: notes, family_summary: summary, follow_ups: followUps }))
                  }
                >
                  Save
                </button>
                {report.status === "open" ? (
                  <button
                    type="button"
                    onClick={() =>
                      void run(() => reviewIncident(report.id, { staff_notes: notes, family_summary: summary, follow_ups: followUps }))
                    }
                  >
                    Mark reviewed
                  </button>
                ) : null}
                <button
                  type="button"
                  disabled={!outcome.trim()}
                  onClick={() =>
                    void run(async () => {
                      await updateIncident(report.id, { staff_notes: notes, follow_ups: followUps });
                      await closeIncident(report.id, { outcome, family_summary: summary || undefined });
                    })
                  }
                >
                  Close with outcome
                </button>
              </>
            )}
          </div>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}
