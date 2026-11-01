"use client";

import { useState } from "react";
import { canWrite, getStoredAuth } from "@/lib/api";
import { VISIT_TYPES, createVisit, type Client, clientName } from "@/lib/opsApi";
import { useMounted } from "@/lib/useMounted";

export function VisitForm({
  clients,
  defaultClientId,
  onSaved,
}: {
  clients: Client[];
  defaultClientId?: number;
  onSaved: () => void;
}) {
  const mounted = useMounted();
  const writable = mounted && canWrite(getStoredAuth()?.role || "");
  const [elderId, setElderId] = useState(defaultClientId ? String(defaultClientId) : "");
  const [visitType, setVisitType] = useState("Baseline profile");
  const [summary, setSummary] = useState("");
  const [status, setStatus] = useState("completed");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (!writable) return null;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!elderId) {
      setError("Choose a client.");
      return;
    }
    setBusy(true);
    try {
      await createVisit({
        elder_id: Number(elderId),
        visit_type: visitType,
        summary,
        status,
        staff_name: getStoredAuth()?.email || "",
        baseline: summary.trim() ? { notes: summary.trim() } : { notes: "Baseline recorded" },
      });
      setSummary("");
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save visit");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel form-grid" onSubmit={onSubmit}>
      <h2>Log a visit</h2>
      {!defaultClientId && (
        <label>
          Client
          <select value={elderId} onChange={(e) => setElderId(e.target.value)} required>
            <option value="">Select client</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>
                {clientName(c)}
              </option>
            ))}
          </select>
        </label>
      )}
      <label>
        Type
        <select value={visitType} onChange={(e) => setVisitType(e.target.value)}>
          {VISIT_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>
      <label>
        Status
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="completed">Completed</option>
          <option value="planned">Planned</option>
        </select>
      </label>
      <label className="span-2">
        Notes
        <textarea
          rows={3}
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          placeholder="What happened, and any follow-up"
        />
      </label>
      {error && <p className="error span-2">{error}</p>}
      <div className="span-2">
        <button type="submit" disabled={busy}>
          {busy ? "Saving…" : status === "completed" ? "Save completed visit" : "Save planned visit"}
        </button>
      </div>
    </form>
  );
}
