"use client";

import { useEffect, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import {
  fetchEmergencyOptions,
  raiseEmergency,
  type EmergencyOptions,
  type Incident,
} from "@/lib/livewell/incidentsApi";

type ClientLite = { id: number; first_name: string; last_name: string; phone?: string | null };

const nameOf = (c: ClientLite) => `${c.first_name} ${c.last_name}`.trim();
const customerIdOf = (id: number) => `KC-${String(id).padStart(6, "0")}`;

/**
 * "Raise emergency" — for a call from a caregiver or the client. Opens a
 * critical incident that shows on Alerts and runs the emergency checklist.
 * Without `elderId` (Alerts page) the form asks which client.
 */
export function RaiseEmergencyButton({
  elderId,
  elderName,
  onRaised,
  className = "danger",
  children,
}: {
  elderId?: number;
  elderName?: string;
  onRaised?: (row: Incident) => void;
  className?: string;
  /** Button content (default "Raise emergency"); header buttons pass icon + label. */
  children?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" className={className} onClick={() => setOpen(true)} aria-label="Raise emergency" title="Raise emergency">
        {children ?? "Raise emergency"}
      </button>
      {open ? (
        <RaiseEmergencyModal
          elderId={elderId}
          elderName={elderName}
          onClose={() => setOpen(false)}
          onRaised={(row) => {
            setOpen(false);
            onRaised?.(row);
          }}
        />
      ) : null}
    </>
  );
}

export function RaiseEmergencyModal({
  elderId,
  elderName,
  onClose,
  onRaised,
}: {
  elderId?: number;
  elderName?: string;
  onClose: () => void;
  onRaised: (row: Incident) => void;
}) {
  const [opts, setOpts] = useState<EmergencyOptions | null>(null);
  const [clients, setClients] = useState<ClientLite[] | null>(null);
  const [client, setClient] = useState<number | "">(elderId ?? "");
  // Find the client by typing (name, phone or customer ID), then confirm before raising.
  const [search, setSearch] = useState("");
  // Three steps: 1 client (search or list), 2 what happened, 3 confirm. A client's own page starts at 2.
  const [step, setStep] = useState<1 | 2 | 3>(elderId === undefined ? 1 : 2);
  const [type, setType] = useState("");
  const [reporter, setReporter] = useState("caregiver");
  const [phone, setPhone] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [loadError, setLoadError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    setLoadError("");
    fetchEmergencyOptions()
      .then(setOpts)
      .catch((e) =>
        setLoadError(
          e instanceof Error && e.message ? e.message : "The server did not answer. Check your connection.",
        ),
      );
    if (elderId === undefined) {
      api<ClientLite[]>("/api/v1/team/clients").then(setClients).catch(() => setClients([]));
    }
  }, [elderId, attempt]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const needNote = type === "other";
  const ready = client !== "" && type && (!needNote || note.trim());
  const chosen = client === "" ? null : (clients || []).find((c) => c.id === client) ?? null;
  const q = search.trim().toLowerCase();
  const matches = (clients || [])
    .filter((c) => !q || `${nameOf(c)} ${c.phone ?? ""} ${customerIdOf(c.id)}`.toLowerCase().includes(q))
    .slice(0, 8);
  const who = elderName || (chosen ? nameOf(chosen) : "this client");
  const missing = [
    client === "" ? "the client" : "",
    !type ? "what happened" : "",
    needNote && !note.trim() ? "a note" : "",
  ].filter(Boolean);

  async function submit() {
    if (!ready || busy) return;
    setBusy(true);
    setError("");
    try {
      const row = await raiseEmergency({
        elder_id: Number(client),
        type,
        reported_by: reporter,
        reporter_phone: reporter !== "caregiver" ? phone.trim() || null : null,
        note: note.trim() || null,
      });
      onRaised(row);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not raise the emergency");
      setBusy(false);
    }
  }

  return (
    <div className="home-safety-showcase-modal-backdrop ks-emg-backdrop" role="presentation" onClick={onClose}>
      <div
        className="home-safety-showcase-modal card ks-emg-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="raise-emg-title"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: 520 }}
      >
        <button type="button" className="ks-emg-x" onClick={onClose} aria-label="Close">
          ×
        </button>
        <h3 id="raise-emg-title" style={{ marginTop: 0, paddingRight: "2.5rem" }}>
          Raise emergency{elderName ? ` — ${elderName}` : ""}
        </h3>
        <p className="muted" style={{ marginTop: 0, marginBottom: "1rem" }}>
          The team is alerted at once. You become the owner until it is closed.
        </p>
        {!opts && loadError ? (
          <div className="ks-emg-loadfail" role="alert">
            <p style={{ margin: 0 }}>
              <strong>Could not load the emergency form.</strong> {loadError}
            </p>
            <p style={{ margin: "0.5rem 0" }}>
              <strong>
                If it&apos;s life-threatening, <a href="tel:108">call 108 now</a>.
              </strong>
            </p>
            <button type="button" className="secondary" onClick={() => setAttempt((n) => n + 1)}>
              Retry
            </button>
          </div>
        ) : !opts ? (
          <p className="muted">Loading…</p>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (step === 3 && ready) void submit();
            }}
            className="ks-emg-form"
          >
            <ol className="ks-emg-steps" aria-label="Steps">
              {(["Client", "What happened", "Confirm"] as const).map((label, i) => (
                <li
                  key={label}
                  className={step === i + 1 ? "is-on" : step > i + 1 ? "is-done" : ""}
                  aria-current={step === i + 1 ? "step" : undefined}
                >
                  <span>{i + 1}</span> {label}
                </li>
              ))}
            </ol>

            {step === 1 ? (
              <>
                <label>
                  Search the client
                  <input
                    type="search"
                    autoFocus
                    placeholder={clients ? "Name, phone or customer ID" : "Loading clients…"}
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </label>
                {q ? (
                  <ul className="ks-emg-results" role="listbox" aria-label="Matching clients">
                    {matches.map((c) => (
                      <li key={c.id}>
                        <button
                          type="button"
                          role="option"
                          aria-selected={client === c.id}
                          onClick={() => {
                            setClient(c.id);
                            setStep(2);
                          }}
                        >
                          <strong>{nameOf(c)}</strong>
                          <small>
                            {customerIdOf(c.id)}
                            {c.phone ? ` · ${c.phone}` : ""}
                          </small>
                        </button>
                      </li>
                    ))}
                    {clients && !matches.length ? <li className="muted">No client matches that search.</li> : null}
                  </ul>
                ) : null}
                <label>
                  Or pick from the list
                  <select
                    value={client}
                    onChange={(e) => {
                      setClient(e.target.value ? Number(e.target.value) : "");
                      if (e.target.value) setStep(2);
                    }}
                  >
                    <option value="">{clients ? "Choose a client" : "Loading…"}</option>
                    {(clients || []).map((c) => (
                      <option key={c.id} value={c.id}>
                        {nameOf(c)} · {customerIdOf(c.id)}
                      </option>
                    ))}
                  </select>
                </label>
              </>
            ) : null}

            {step === 2 ? (
              <>
                <div className="ks-emg-chosen">
                  <span>
                    <strong>{who}</strong> {client !== "" ? <small>{customerIdOf(Number(client))}</small> : null}
                  </span>
                  {elderId === undefined ? (
                    <button type="button" className="secondary" onClick={() => setStep(1)}>
                      Change
                    </button>
                  ) : null}
                </div>
                <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
                  <legend className="ks-emg-legend">What happened</legend>
                  <div className="ks-emg-types">
                    {opts.types.map((t) => (
                      <button
                        key={t.value}
                        type="button"
                        className={type === t.value ? "danger" : "secondary"}
                        aria-pressed={type === t.value}
                        onClick={() => setType(t.value)}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                </fieldset>
                <label>
                  Who told us
                  <select value={reporter} onChange={(e) => setReporter(e.target.value)}>
                    {opts.reporters.map((r) => (
                      <option key={r.value} value={r.value}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                </label>
                {reporter !== "caregiver" ? (
                  <label>
                    Their phone (optional)
                    <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} maxLength={40} />
                  </label>
                ) : null}
                <label>
                  Reason / note{needNote ? " (required)" : " (optional)"}
                  <textarea rows={3} value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} />
                </label>
              </>
            ) : null}

            {step === 3 ? (
              <div className="ks-emg-summary" role="group" aria-label="Check before raising">
                <dl>
                  <div>
                    <dt>Client</dt>
                    <dd>{who}</dd>
                  </div>
                  <div>
                    <dt>What happened</dt>
                    <dd>{opts.types.find((t) => t.value === type)?.label ?? ""}</dd>
                  </div>
                  <div>
                    <dt>Who told us</dt>
                    <dd>
                      {opts.reporters.find((r) => r.value === reporter)?.label ?? reporter}
                      {phone.trim() ? ` · ${phone.trim()}` : ""}
                    </dd>
                  </div>
                  {note.trim() ? (
                    <div>
                      <dt>Note</dt>
                      <dd>{note.trim()}</dd>
                    </div>
                  ) : null}
                </dl>
                <p className="ks-emg-confirm" role="alert">
                  Their care team, the heads and their family will hear the siren straight away.
                </p>
              </div>
            ) : null}

            {error ? <p className="error">{error}</p> : null}
            <div className="ks-emg-actions">
              {step === 1 || (step === 2 && elderId !== undefined) ? (
                <button type="button" className="secondary" onClick={onClose} disabled={busy}>
                  Cancel
                </button>
              ) : (
                <button type="button" className="secondary" onClick={() => setStep(step === 3 ? 2 : 1)} disabled={busy}>
                  Back
                </button>
              )}
              {/* Distinct keys: React must not turn the "Next" being tapped into the submit
                  button mid-tap, or that same tap raises the emergency without the confirm step. */}
              {step === 1 ? (
                <button key="next-1" type="button" className="danger" disabled={client === ""} onClick={() => setStep(2)}>
                  Next
                </button>
              ) : step === 2 ? (
                <button key="next-2" type="button" className="danger" disabled={!ready} onClick={() => setStep(3)}>
                  Next
                </button>
              ) : (
                <button key="confirm" type="submit" className="danger" disabled={!ready || busy}>
                  {busy ? "Raising…" : "Confirm — raise emergency"}
                </button>
              )}
            </div>
            {step === 2 && !ready && missing.length ? (
              <p className="muted ks-emg-hint">To continue, choose {missing.join(" and ")}.</p>
            ) : null}
          </form>
        )}
      </div>
    </div>
  );
}
