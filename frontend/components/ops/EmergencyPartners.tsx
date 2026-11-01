"use client";

import { useEffect, useState } from "react";
import {
  fetchEmergencyPartners,
  saveEmergencyPartners,
  type EmergencyPartner,
} from "@/lib/livewell/incidentsApi";

type Draft = Omit<EmergencyPartner, "id"> & { id?: string };

const BLANK: Draft = { name: "", phone: "", email: "", type: "ambulance" };
const TYPES: { value: EmergencyPartner["type"]; label: string }[] = [
  { value: "ambulance", label: "Ambulance" },
  { value: "hospital", label: "Hospital" },
  { value: "internal", label: "Our own team" },
];

/** Settings → Emergency partners: who "Notify partner" emails during an emergency. */
export function EmergencyPartners({ canEdit }: { canEdit: boolean }) {
  const [partners, setPartners] = useState<EmergencyPartner[] | null>(null);
  const [idle, setIdle] = useState(10);
  const [draft, setDraft] = useState<Draft>(BLANK);
  const [status, setStatus] = useState("");
  const [loadError, setLoadError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    setLoadError("");
    fetchEmergencyPartners()
      .then((r) => {
        setPartners(r.partners);
        setIdle(r.idle_minutes);
      })
      .catch((e) =>
        setLoadError(e instanceof Error && e.message ? e.message : "The server did not answer."),
      );
  }, [attempt]);

  async function save(body: { partners?: Draft[]; idle_minutes?: number }) {
    setStatus("Saving…");
    try {
      const r = await saveEmergencyPartners(body);
      setPartners(r.partners);
      setIdle(r.idle_minutes);
      setStatus("Saved");
      return true;
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Could not save");
      return false;
    }
  }

  if (!partners) {
    return (
      <section className="card" aria-labelledby="emg-partners-title">
        <div className="ks-email-head">
          <h2 id="emg-partners-title">Emergency partners</h2>
        </div>
        {loadError ? (
          <div role="alert">
            <p className="error" style={{ marginTop: 0 }}>
              Could not load emergency partners. {loadError}
            </p>
            <button type="button" className="secondary" onClick={() => setAttempt((n) => n + 1)}>
              Retry
            </button>
          </div>
        ) : (
          <p className="muted">Loading…</p>
        )}
      </section>
    );
  }

  return (
    <section className="card" aria-labelledby="emg-partners-title">
      <div className="ks-email-head">
        <h2 id="emg-partners-title">Emergency partners</h2>
        {status && <small aria-live="polite">{status}</small>}
      </div>
      <p className="muted">
        Ambulance services and hospitals the team can hand an emergency to. &ldquo;Notify partner&rdquo; emails them a
        link (valid 48 hours) to reply Received, On the way or Done. SMS is not connected yet, so add an email.
      </p>
      {partners.length === 0 ? <p className="muted">No partners yet.</p> : null}
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "0.4rem" }}>
        {partners.map((p) => (
          <li key={p.id} style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
            <strong>{p.name}</strong>
            <span className="muted">
              {TYPES.find((t) => t.value === p.type)?.label} · {p.phone || "no phone"} · {p.email || "no email"}
            </span>
            {canEdit ? (
              <button
                type="button"
                className="secondary"
                onClick={() => void save({ partners: partners.filter((x) => x.id !== p.id) })}
              >
                Remove
              </button>
            ) : null}
          </li>
        ))}
      </ul>
      {canEdit ? (
        <form
          style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.75rem" }}
          onSubmit={async (e) => {
            e.preventDefault();
            if (!draft.name.trim()) return;
            if (await save({ partners: [...partners, draft] })) setDraft(BLANK);
          }}
        >
          <input
            placeholder="Name"
            aria-label="Partner name"
            value={draft.name}
            maxLength={200}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          />
          <select
            aria-label="Partner type"
            value={draft.type}
            onChange={(e) => setDraft({ ...draft, type: e.target.value as EmergencyPartner["type"] })}
          >
            {TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
          <input
            placeholder="Phone"
            aria-label="Partner phone"
            type="tel"
            value={draft.phone}
            maxLength={40}
            onChange={(e) => setDraft({ ...draft, phone: e.target.value })}
          />
          <input
            placeholder="Email"
            aria-label="Partner email"
            type="email"
            value={draft.email}
            maxLength={255}
            onChange={(e) => setDraft({ ...draft, email: e.target.value })}
          />
          <button type="submit" className="secondary" disabled={!draft.name.trim()}>
            Add partner
          </button>
        </form>
      ) : null}
      <p style={{ marginTop: "0.75rem" }}>
        <label>
          If nobody works on an emergency for{" "}
          <select
            className="nt-min"
            value={idle}
            disabled={!canEdit}
            aria-label="Minutes"
            onChange={(e) => void save({ idle_minutes: Number(e.target.value) })}
          >
            {[5, 10, 15, 20, 30].map((m) => (
              <option key={m} value={m}>
                {m} min
              </option>
            ))}
          </select>{" "}
          it goes up the escalation list.
        </label>
      </p>
    </section>
  );
}
