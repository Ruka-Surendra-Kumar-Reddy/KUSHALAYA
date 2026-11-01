"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { formatIST } from "@/lib/ist";
import {
  acknowledgeIncident,
  fetchIncidents,
  INCIDENT_OUTCOMES,
  resolveIncident,
  type Incident,
  type IncidentOutcome,
} from "@/lib/livewell/incidentsApi";
import { can } from "@/lib/roles";

/** Client page → SOS & alerts: this client's open alerts with Acknowledge / Close.
 *  Emergencies (staff-raised) keep their own close flow on the Alerts page. */
export function ClientAlertsPanel({ elderId, onChanged }: { elderId: number; onChanged?: () => void }) {
  const [rows, setRows] = useState<Incident[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<number | null>(null);
  const [closing, setClosing] = useState<number | null>(null);
  const [outcome, setOutcome] = useState<IncidentOutcome>(INCIDENT_OUTCOMES[0].value);
  const [note, setNote] = useState("");

  const load = useCallback(() => {
    fetchIncidents()
      .then((all) => setRows(all.filter((i) => i.elder_id === elderId)))
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load alerts"));
  }, [elderId]);

  useEffect(() => load(), [load]);

  async function run(id: number, action: () => Promise<unknown>) {
    setBusy(id);
    setError("");
    try {
      await action();
      setClosing(null);
      setNote("");
      load();
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy(null);
    }
  }

  const canEdit = can("edit");
  return (
    <section className="card cp-sos">
      <h2>Open now</h2>
      {error ? <p className="error-text">{error}</p> : null}
      {rows === null ? (
        <p className="muted">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="muted">Nothing open for this client.</p>
      ) : (
        <ul className="cp-sos-list">
          {rows.map((i) => (
            <li key={i.id} className={`cp-sos-row${i.severity === "critical" ? " is-critical" : ""}`}>
              <div className="cp-sos-head">
                <strong>{i.kind_label}</strong>
                <span className={`cp-pill cp-pill-${i.status}`}>{i.status.replace(/^./, (c) => c.toUpperCase())}</span>
                <span className="muted">
                  {formatIST(i.opened_at)} · open {i.minutes_open} min
                  {i.acknowledged_by ? ` · seen by ${i.acknowledged_by}` : ""}
                </span>
              </div>
              {i.note ? <p className="cp-sos-note">{i.note}</p> : null}
              <div className="cp-sos-actions">
                {canEdit && i.status === "open" ? (
                  <button type="button" disabled={busy === i.id} onClick={() => void run(i.id, () => acknowledgeIncident(i.id))}>
                    Acknowledge
                  </button>
                ) : null}
                {!canEdit || i.kind === "staff_emergency" ? null : closing === i.id ? null : (
                  <button type="button" className="secondary" onClick={() => setClosing(i.id)}>
                    Close
                  </button>
                )}
                <Link className="secondary" href={`/kushalaya/alerts?open=${i.id}`}>
                  {i.kind === "staff_emergency" ? "Open emergency" : "Open in alerts"}
                </Link>
              </div>
              {closing === i.id ? (
                <div className="cp-sos-close">
                  <select value={outcome} onChange={(e) => setOutcome(e.target.value as IncidentOutcome)} aria-label="Outcome">
                    {INCIDENT_OUTCOMES.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                  <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="What happened (optional)" maxLength={1000} />
                  <button
                    type="button"
                    className="primary"
                    disabled={busy === i.id}
                    onClick={() => void run(i.id, () => resolveIncident(i.id, outcome, note || undefined))}
                  >
                    Close alert
                  </button>
                  <button type="button" className="secondary" onClick={() => setClosing(null)}>
                    Cancel
                  </button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
