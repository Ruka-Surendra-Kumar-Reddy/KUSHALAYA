"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CareJob } from "@/lib/jobs";
import { markPressedHere } from "@/lib/sos-siren";

type Option = { value: string; label: string };

export type MyEmergency = {
  id: number;
  elder_id: number;
  status: string;
  type_label: string | null;
  opened_at: string;
  owner_name: string | null;
  steps_done: string[];
  outcome: string | null;
  created?: boolean;
};

export function myEmergencies() {
  return api<MyEmergency[]>("/api/v1/caregiver-portal/emergency");
}

/** Caregiver raises an emergency on a client from a visit card. */
export function EmergencySheet({
  job,
  onClose,
  onDone,
}: {
  job: CareJob;
  onClose: () => void;
  onDone: (msg: string) => void;
}) {
  const [opts, setOpts] = useState<{ types: Option[]; reporters: Option[] } | null>(null);
  const [type, setType] = useState("");
  const [reporter, setReporter] = useState("caregiver");
  const [phone, setPhone] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ types: Option[]; reporters: Option[] }>("/api/v1/caregiver-portal/emergency/options")
      .then(setOpts)
      .catch(() => setError("Could not load. Call your care manager now."));
  }, []);

  const ready = type && (type !== "other" || note.trim());

  async function submit() {
    if (!ready || busy) return;
    setBusy(true);
    setError("");
    try {
      markPressedHere(); // this phone stays quiet for its own SOS
      const row = await api<MyEmergency>("/api/v1/caregiver-portal/emergency", {
        method: "POST",
        body: JSON.stringify({
          elder_id: job.elder_id,
          job_id: job.id,
          type,
          reported_by: reporter,
          reporter_phone: phone.trim() || null,
          note: note.trim() || null,
        }),
      });
      onDone(
        row.created === false
          ? `The team already has an emergency open for ${job.elder_name}; your report was added.`
          : `Emergency raised for ${job.elder_name}. The care team has been alerted${row.owner_name ? ` — ${row.owner_name} is handling it` : ""}.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not raise it. Call your care manager now.");
      setBusy(false);
    }
  }

  return (
    <div className="cg-app cg-sheet" role="dialog" aria-label="Raise emergency">
      <div className="cg-sheet-card">
        <div className="cg-sheet-head">
          <strong>Emergency — {job.elder_name}</strong>
          <button type="button" className="cg-sheet-x" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <p className="cg-hint">If life is in danger, call 108 first. Then tell the team here.</p>
        {opts ? (
          <>
            <p className="cg-field">What happened</p>
            <div className="cg-emg-types">
              {opts.types.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  className={`cg-btn ${type === t.value ? "cg-emg-on" : "is-ghost"}`}
                  aria-pressed={type === t.value}
                  onClick={() => setType(t.value)}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <label className="cg-field">
              Who told you
              <select value={reporter} onChange={(e) => setReporter(e.target.value)}>
                {opts.reporters.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </label>
            {reporter !== "caregiver" ? (
              <label className="cg-field">
                Their phone (optional)
                <input type="tel" value={phone} maxLength={40} onChange={(e) => setPhone(e.target.value)} />
              </label>
            ) : null}
            <label className="cg-field">
              Note{type === "other" ? " (required)" : ""}
              <textarea rows={3} value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} placeholder="What you see, and what you have done" />
            </label>
          </>
        ) : null}
        {error ? <p className="cg-note is-warn">{error}</p> : null}
        <button type="button" className="cg-btn cg-emg-on cg-sheet-submit" disabled={!ready || busy} onClick={() => void submit()}>
          {busy ? "Raising…" : "Raise emergency"}
        </button>
      </div>
    </div>
  );
}
