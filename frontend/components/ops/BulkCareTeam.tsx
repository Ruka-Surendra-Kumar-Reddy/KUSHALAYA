"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export type BulkAction = "manager" | "caregiver";
type Person = { id: number; first_name: string; last_name: string };
type Result = { done: { elder_id: number; name: string }[]; failed: { elder_id: number; name: string; reason: string }[] };

const full = (p: Person) => `${p.first_name} ${p.last_name || ""}`.trim();

/** Clients list: change the care manager of / add a caregiver to several clients at once. */
export function BulkCareTeamDialog({
  action,
  clients,
  onClose,
  onDone,
}: {
  action: BulkAction;
  clients: { id: number; name: string }[];
  onClose: () => void;
  onDone: () => void;
}) {
  const [people, setPeople] = useState<Person[]>([]);
  const [pick, setPick] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    api<Person[]>(action === "manager" ? "/api/v1/team/managers" : "/api/v1/team/caregivers")
      .then(setPeople)
      .catch(() => setError("Could not load the list"));
  }, [action]);

  const picked = people.find((p) => String(p.id) === pick);
  const title = action === "manager" ? "Change care manager" : "Assign caregiver";
  const names = names3(clients.map((c) => c.name));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api<Result>("/api/v1/team/clients/bulk-care-team", {
        method: "POST",
        body: JSON.stringify({
          elder_ids: clients.map((c) => c.id),
          action,
          manager_user_id: action === "manager" ? Number(pick) : null,
          caregiver_id: action === "caregiver" ? Number(pick) : null,
          note: note.trim() || null,
        }),
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  function close() {
    if (result) onDone();
    onClose();
  }

  return (
    <div className="home-safety-showcase-modal-backdrop" role="presentation" onClick={close}>
      <form
        className="home-safety-showcase-modal card ct-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
      >
        <h2>{title}</h2>
        {result ? (
          <div role="status">
            <p>
              Done for {result.done.length} of {clients.length} client{clients.length === 1 ? "" : "s"}.
            </p>
            {result.failed.length ? (
              <>
                <p>
                  <strong>Not changed ({result.failed.length}):</strong>
                </p>
                <ul>
                  {result.failed.map((f) => (
                    <li key={f.elder_id}>
                      {f.name || `Client ${f.elder_id}`}: {f.reason}
                    </li>
                  ))}
                </ul>
              </>
            ) : null}
            <div className="ct-dialog-actions">
              <button type="button" className="ct-btn" onClick={close}>
                Close
              </button>
            </div>
          </div>
        ) : (
          <>
            <p>
              For {clients.length} client{clients.length === 1 ? "" : "s"}: {names}
            </p>
            <label className="ct-field">
              {action === "manager" ? "New care manager" : "Caregiver to add"}
              <select value={pick} onChange={(e) => setPick(e.target.value)} required>
                <option value="">Choose…</option>
                {people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {full(p)}
                  </option>
                ))}
              </select>
            </label>
            {action === "manager" ? (
              <label className="ct-field">
                Handover note (optional)
                <textarea rows={3} value={note} maxLength={4000} onChange={(e) => setNote(e.target.value)} />
              </label>
            ) : null}
            {picked ? (
              <p className="muted">
                {action === "manager"
                  ? `${full(picked)} becomes the care manager and gets a handover note for each client.`
                  : `${full(picked)} is added as a regular caregiver. Booked visits are not changed.`}
              </p>
            ) : null}
            {error ? (
              <p className="error" role="alert">
                {error}
              </p>
            ) : null}
            <div className="ct-dialog-actions">
              <button type="button" className="secondary ct-btn" onClick={onClose} disabled={busy}>
                Cancel
              </button>
              <button type="submit" className="ct-btn" disabled={busy || !pick}>
                {busy ? "Saving…" : "Confirm"}
              </button>
            </div>
          </>
        )}
      </form>
    </div>
  );
}

function names3(list: string[]): string {
  return list.length <= 3 ? list.join(", ") : `${list.slice(0, 3).join(", ")} and ${list.length - 3} more`;
}
