"use client";

import { useState } from "react";
import type { CareJob } from "@/lib/jobs";
import { fileCaregiverIncident, INCIDENT_KINDS, isSerious, localToIso } from "@/lib/incident-reports";
import "./caregiver.css";

/** Caregiver files an incident report (fall, near-miss, medicine mistake…) on one of their visits. */
export function IncidentSheet({ job, onClose, onDone }: { job: CareJob; onClose: () => void; onDone: (msg: string) => void }) {
  const [kind, setKind] = useState("");
  const [what, setWhat] = useState("");
  const [when, setWhen] = useState("");
  const [where, setWhere] = useState("");
  const [injury, setInjury] = useState("");
  const [action, setAction] = useState("");
  const [witnesses, setWitnesses] = useState("");
  const [told, setTold] = useState(false);
  const [toldAt, setToldAt] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const serious = isSerious(kind, injury);

  async function submit() {
    if (!kind || !what.trim()) {
      setError("Pick what happened and describe it.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const r = await fileCaregiverIncident(job.id, {
        kind,
        what_happened: what.trim(),
        occurred_at: localToIso(when),
        location: where.trim(),
        injury: injury.trim(),
        action_taken: action.trim(),
        witnesses: witnesses.trim(),
        family_informed: told,
        family_informed_at: told ? localToIso(toldAt) : null,
      });
      onDone(
        r.serious
          ? `Report sent. Your care manager has been told straight away.`
          : `Report sent to your care manager. Thank you.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not send the report");
      setBusy(false);
    }
  }

  return (
    <div className="cg-app cg-sheet" role="dialog" aria-label="Incident report">
      <div className="cg-sheet-card">
        <div className="cg-sheet-head">
          <strong>Incident report — {job.elder_name}</strong>
          <button type="button" className="cg-sheet-x" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <p className="cg-hint">For something that already happened. If someone is hurt now, use Emergency.</p>
        <p className="cg-field">What kind</p>
        <div className="cg-emg-types">
          {INCIDENT_KINDS.map((k) => (
            <button
              key={k.value}
              type="button"
              className={`cg-btn ${kind === k.value ? "is-out" : "is-ghost"}`}
              aria-pressed={kind === k.value}
              onClick={() => setKind(k.value)}
            >
              {k.label}
            </button>
          ))}
        </div>
        <label className="cg-field">
          What happened
          <textarea rows={3} value={what} maxLength={4000} onChange={(e) => setWhat(e.target.value)} />
        </label>
        <label className="cg-field">
          When (leave empty for now)
          <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} />
        </label>
        <label className="cg-field">
          Where
          <input value={where} maxLength={300} onChange={(e) => setWhere(e.target.value)} placeholder="e.g. bathroom" />
        </label>
        <label className="cg-field">
          Injury (empty if none)
          <input value={injury} maxLength={2000} onChange={(e) => setInjury(e.target.value)} />
        </label>
        <label className="cg-field">
          What you did
          <textarea rows={2} value={action} maxLength={2000} onChange={(e) => setAction(e.target.value)} />
        </label>
        <label className="cg-field">
          Who saw it
          <input value={witnesses} maxLength={500} onChange={(e) => setWitnesses(e.target.value)} />
        </label>
        <label className="cg-toggle">
          <input type="checkbox" checked={told} onChange={(e) => setTold(e.target.checked)} />
          Family already told
        </label>
        {told ? (
          <label className="cg-field">
            When they were told
            <input type="datetime-local" value={toldAt} onChange={(e) => setToldAt(e.target.value)} />
          </label>
        ) : null}
        {serious ? <p className="cg-note is-warn">This is serious: your care manager is told as soon as you send it.</p> : null}
        {error ? <p className="cg-note is-warn">{error}</p> : null}
        <button type="button" className="cg-btn is-out cg-sheet-submit" disabled={busy} onClick={() => void submit()}>
          {busy ? "Sending…" : "Send report"}
        </button>
      </div>
    </div>
  );
}
