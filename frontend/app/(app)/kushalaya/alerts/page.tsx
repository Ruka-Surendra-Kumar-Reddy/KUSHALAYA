"use client";

import { whenIST } from "@/lib/ist";
import { INCIDENT_PREFILL_KEY } from "@/components/ops/ClientIncidents";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import "@/components/ops/alerts.css";

import { RaiseEmergencyButton } from "@/components/ops/RaiseEmergency";
import { can, isAdmin } from "@/lib/roles";
import { PageHeader } from "@/components/PageHeader";
import { SmsOffBanner } from "@/components/ops/SmsOffBanner";
import { Directions } from "@/components/Directions";
import { formatIST } from "@/lib/ist";
import {
  acknowledgeIncident,
  closeEmergency,
  confirmSos,
  escalateIncident,
  falseAlarmSos,
  fetchEmergencyOptions,
  fetchIncident,
  fetchIncidents,
  INCIDENT_OUTCOMES,
  noteIncident,
  notifyEmergencyPartner,
  notifySosFamily,
  resolveIncident,
  takeEmergencyOwnership,
  tickEmergencyStep,
  type EmergencyOptions,
  type Incident,
  type IncidentEvent,
  type IncidentOutcome,
} from "@/lib/livewell/incidentsApi";

const REFRESH_MS = 30_000;

const isEmergency = (r: Incident) => r.kind === "staff_emergency";
const isOpenRow = (r: Incident) => r.status !== "resolved" && r.status !== "closed";

/** "10:42 am" today, "Thu 8 Oct, 10:42 am" on an older day (India time). */
function istTime(iso: string | null | undefined): string {
  return whenIST(iso);
}

/** sessionStorage hand-off to the client's Incidents tab (see ClientIncidents). */
function startIncidentReport(r: Incident, note: string) {
  const d = r.details || {};
  const local = (iso: string | null | undefined) => {
    if (!iso) return "";
    const t = new Date(iso);
    return Number.isNaN(t.getTime()) ? "" : new Date(t.getTime() + 330 * 60000).toISOString().slice(0, 16);
  };
  const hospital = d.hospital_name ? ` Taken to ${d.hospital_name}.` : "";
  try {
    sessionStorage.setItem(
      INCIDENT_PREFILL_KEY,
      JSON.stringify({
        elder_id: r.elder_id,
        kind: r.kind === "fall" ? "fall" : "other",
        occurred_at: local(r.opened_at),
        what_happened: `${whatHappened(r)}. Admitted to hospital.${hospital}${note ? ` ${note}` : ""}`.slice(0, 4000),
        action_taken: `Emergency handled and closed as a hospital admission${d.hospital_name ? ` (${d.hospital_name})` : ""}.`,
        serious: true,
      }),
    );
  } catch {
    /* storage blocked: the form opens empty */
  }
}

function ago(min: number): string {
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (h < 24) return m ? `${h} h ${m} min ago` : `${h} h ago`;
  return `${Math.floor(h / 24)} d ${h % 24} h ago`;
}

function duration(min: number): string {
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  if (h < 24) return m ? `${h} h ${m} min` : `${h} h`;
  return `${Math.floor(h / 24)} d ${h % 24} h`;
}

/** What happened, in plain words. */
function whatHappened(r: Incident): string {
  const who = r.elder_name || `Client #${r.elder_id}`;
  switch (r.kind) {
    case "sos_button":
      return `${who} pressed the SOS button on their wearable`;
    case "fall":
      return `${who} may have fallen (wearable)`;
    case "immobility":
      return `${who} has not moved for a long time (wearable)`;
    case "device_offline":
      return `${who}'s band is offline`;
    case "battery_low":
      return `${who}'s wearable battery is low`;
    case "family_sos":
      return `${who}'s family asked for urgent help`;
    case "staff_emergency": {
      const d = r.details || {};
      const by = d.reported_by_label ? `, reported by ${d.reported_by_label.toLowerCase()}` : "";
      return `Emergency for ${who}: ${d.type_label || "other"}${by}`;
    }
    default:
      return `${r.kind_label} for ${who}`;
  }
}

/** Where it stands, in plain words. */
function whereItStands(r: Incident): string {
  if (!isOpenRow(r)) {
    const outcome = r.outcome ? OUTCOME_WORDS[r.outcome] || r.outcome.replace(/_/g, " ") : "closed";
    return `Closed (${outcome})${r.resolved_by ? ` by ${r.resolved_by}` : ""}${r.resolved_at ? ` at ${istTime(r.resolved_at)}` : ""}`;
  }
  const parts: string[] = [];
  if (isEmergency(r)) {
    parts.push(r.owner_name ? `Owner: ${r.owner_name}` : "No owner yet");
  } else if (r.acknowledged_at) {
    parts.push(`Acknowledged by ${r.acknowledged_by || "staff"} at ${istTime(r.acknowledged_at)}`);
  } else {
    parts.push("Nobody has acknowledged it yet");
  }
  if (r.escalation_level) parts.push(`escalated (step ${r.escalation_level})`);
  return parts.join(" · ");
}

const OUTCOME_WORDS: Record<string, string> = {
  hospital_admission: "admitted to hospital",
  resolved_home: "resolved at home",
  false_alarm: "false alarm",
  family_resolved: "family said they're OK",
};

const EVENT_LABELS: Record<string, string> = {
  received: "Received",
  acknowledged: "Acknowledged",
  escalated: "Escalated",
  contacted: "Contacted",
  resolved: "Closed",
  closed: "Closed",
  note: "Note",
  raised: "Emergency raised",
  opened: "Emergency raised",
  step: "Step done",
  assigned: "Owner",
  partner: "Partner",
};

function eventLabel(e: IncidentEvent): string {
  if (e.event === "notified") {
    const where = [e.channel, e.recipient].filter(Boolean).join(" → ");
    return `${e.ok ? "Notified" : "Notification failed"}${where ? ` (${where})` : ""}`;
  }
  return EVENT_LABELS[e.event] || e.event;
}

/** snake_case codes in event details → plain words ("call_elder" → "call elder"). */
function plainWords(text: string): string {
  return text.replace(/\b([a-z]+(?:_[a-z]+)+)\b/g, (m) => m.replace(/_/g, " "));
}

/** One plain sentence per event: "Raised by Anita Rao", never a raw code or a name twice. */
function eventSentence(e: IncidentEvent): string {
  const actor = (e.actor_name || "").trim();
  const detail = plainWords((e.detail || "").trim());
  if (e.event === "notified") return detail ? `${eventLabel(e)}: ${detail}` : eventLabel(e);
  if (e.event === "note") return `${actor || "Staff"} added a note${detail ? `: ${detail}` : ""}`;
  const label = EVENT_LABELS[e.event] || plainWords(e.event).replace(/^./, (c) => c.toUpperCase());
  const main = detail || label;
  if (!actor || main.toLowerCase().includes(actor.toLowerCase())) return main;
  return detail ? `${main} (${actor})` : `${main} by ${actor}`;
}

function Timeline({ events }: { events: IncidentEvent[] | undefined }) {
  if (!events) return <p className="muted">Loading timeline…</p>;
  if (events.length === 0) return <p className="muted">No events yet.</p>;
  return (
    <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {events.map((e) => (
        <li
          key={e.id}
          title={formatIST(e.at)}
          style={{
            padding: "0.35rem 0",
            borderBottom: "1px solid var(--border)",
            fontSize: "0.9rem",
            overflowWrap: "anywhere",
          }}
        >
          <span style={{ color: e.ok ? undefined : "var(--danger)", fontWeight: e.ok ? undefined : 600 }}>
            {eventSentence(e)}
          </span>
          <span className="muted"> · {istTime(e.at)}</span>
        </li>
      ))}
    </ul>
  );
}

function PhoneIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.4 1.8.7 2.7a2 2 0 0 1-.5 2.1L8 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.7.7a2 2 0 0 1 1.7 2z" />
    </svg>
  );
}

function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="home-safety-showcase-modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="home-safety-showcase-modal card"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: 520 }}
      >
        <button type="button" className="home-safety-showcase-modal-close" onClick={onClose} aria-label="Close">
          ×
        </button>
        <h3 style={{ marginTop: 0 }}>{title}</h3>
        {children}
      </div>
    </div>
  );
}

function ResolveModal({
  incident,
  options,
  busy,
  onClose,
  onSubmit,
}: {
  incident: Incident;
  options: EmergencyOptions | null;
  busy: boolean;
  onClose: () => void;
  onSubmit: (outcome: string, note: string) => void;
}) {
  const emergency = isEmergency(incident);
  const choices = emergency
    ? options?.outcomes || []
    : INCIDENT_OUTCOMES.map((o) => ({ value: o.value as string, label: o.label }));
  const [outcome, setOutcome] = useState<string>(emergency ? "" : "contacted_family");
  const [note, setNote] = useState("");
  const noteRequired = emergency || outcome === "other";
  const ready = outcome && (!noteRequired || note.trim());

  return (
    <Modal title={`${emergency ? "Close emergency" : "Close alert"} — ${incident.elder_name || `Client #${incident.elder_id}`}`} onClose={onClose}>
      <p className="muted" style={{ marginTop: 0 }}>
        {whatHappened(incident)} · open {duration(incident.minutes_open)}
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (ready) onSubmit(outcome, note.trim());
        }}
      >
        <label htmlFor="resolve-outcome">Outcome</label>
        <select
          id="resolve-outcome"
          value={outcome}
          onChange={(e) => setOutcome(e.target.value)}
          style={{ width: "100%", marginBottom: "0.75rem" }}
        >
          {emergency ? <option value="">Choose the outcome</option> : null}
          {choices.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <label htmlFor="resolve-note">Note{noteRequired ? " (required)" : ""}</label>
        <textarea
          id="resolve-note"
          rows={3}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="What happened and who was reached"
          style={{ width: "100%", marginBottom: "0.75rem" }}
        />
        {emergency ? (
          <p className="muted" style={{ marginTop: 0 }}>
            The family sees only the outcome, not this note.
          </p>
        ) : null}
        <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
          <button type="button" className="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="submit" disabled={busy || !ready}>
            {busy ? "Saving…" : emergency ? "Close emergency" : "Close alert"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function ConfirmEscalate({
  incident,
  busy,
  onClose,
  onConfirm,
}: {
  incident: Incident;
  busy: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const next = Math.min(3, (incident.escalation_level || 0) + 1);
  return (
    <Modal title="Escalate now?" onClose={onClose}>
      <p>
        {whatHappened(incident)}. This alerts the next step of the escalation list (step {next})
        by email and phone, straight away.
      </p>
      <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
        <button type="button" className="secondary" onClick={onClose} disabled={busy}>
          Cancel
        </button>
        <button type="button" className="danger" onClick={onConfirm} disabled={busy}>
          {busy ? "Escalating…" : "Yes, escalate"}
        </button>
      </div>
    </Modal>
  );
}

/** Checklist, owner and partner hand-off for a staff-raised emergency. */
function EmergencyPanel({
  incident,
  options,
  busy,
  run,
}: {
  incident: Incident;
  options: EmergencyOptions | null;
  busy: boolean;
  run: (action: () => Promise<Incident>) => void;
}) {
  const [hospital, setHospital] = useState(incident.details?.hospital_name || "");
  const [partner, setPartner] = useState("");
  const steps = incident.details?.steps || {};
  // Actions only for staff who can change things; view-only staff see the record.
  const open = isOpenRow(incident) && can("edit");
  const d = incident.details || {};

  return (
    <div style={{ display: "grid", gap: "0.75rem", marginBottom: "0.75rem" }}>
      <p style={{ margin: 0 }}>
        <strong>Reported by:</strong> {d.reported_by_label || "—"}
        {d.reporter_phone ? (
          <>
            {" "}
            · <a href={`tel:${d.reporter_phone}`}>{d.reporter_phone}</a>
          </>
        ) : null}
        {d.raised_by_name ? <span className="muted"> · raised by {d.raised_by_name}</span> : null}
      </p>
      <p style={{ margin: 0 }}>
        <strong>Owner:</strong> {incident.owner_name || "nobody"}{" "}
        {open ? (
          <button type="button" className="secondary" disabled={busy} onClick={() => run(() => takeEmergencyOwnership(incident.id))}>
            Take over
          </button>
        ) : null}
      </p>
      <div>
        <strong>Checklist</strong>
        <ul style={{ listStyle: "none", margin: "0.35rem 0 0", padding: 0, display: "grid", gap: "0.35rem" }}>
          {(options?.steps || []).map((s) => {
            const done = steps[s.value];
            return (
              <li key={s.value} style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
                <span aria-hidden="true">{done ? "✓" : "○"}</span>
                <span style={{ fontWeight: done ? 600 : undefined }}>{s.label}</span>
                {done ? (
                  <span className="muted">
                    {done.by_name} at {istTime(done.at)}
                    {done.hospital_name ? ` · ${done.hospital_name}` : ""}
                    {done.note && s.value !== "partner_notified" ? ` · ${done.note}` : ""}
                  </span>
                ) : null}
                {open && !done && s.value === "ambulance" ? (
                  <input
                    type="text"
                    placeholder="Hospital name"
                    value={hospital}
                    onChange={(e) => setHospital(e.target.value)}
                    maxLength={200}
                    aria-label="Hospital name"
                  />
                ) : null}
                {open && !done && s.value !== "partner_notified" ? (
                  <button
                    type="button"
                    className="secondary"
                    disabled={busy || (s.value === "ambulance" && !hospital.trim())}
                    onClick={() =>
                      run(() =>
                        tickEmergencyStep(incident.id, s.value, s.value === "ambulance" ? { hospital_name: hospital.trim() } : {}),
                      )
                    }
                  >
                    Done
                  </button>
                ) : null}
              </li>
            );
          })}
        </ul>
      </div>
      <div>
        <strong>Partners</strong>
        {incident.partners && incident.partners.length ? (
          <ul style={{ margin: "0.35rem 0", paddingLeft: "1.1rem" }}>
            {incident.partners.map((p) => (
              <li key={p.id}>
                {p.name} — {p.last_status_label ? `${p.last_status_label} at ${istTime(p.last_response_at)}` : `told at ${istTime(p.sent_at)}, no reply yet`}
                {p.phone ? (
                  <>
                    {" "}
                    · <a href={`tel:${p.phone}`}>{p.phone}</a>
                  </>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted" style={{ margin: "0.35rem 0" }}>
            No partner told yet.
          </p>
        )}
        {open ? (
          options && options.partners.length ? (
            <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              <select value={partner} onChange={(e) => setPartner(e.target.value)} aria-label="Partner">
                <option value="">Choose a partner</option>
                {options.partners.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.type})
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="secondary"
                disabled={busy || !partner}
                onClick={() => run(() => notifyEmergencyPartner(incident.id, partner))}
              >
                Notify partner
              </button>
            </div>
          ) : (
            <p className="muted" style={{ margin: 0 }}>
              {isAdmin()
                ? "Add ambulance and hospital partners in Settings → Notifications & SOS → Emergency partners."
                : "No emergency partners are set up."}
            </p>
          )
        ) : null}
      </div>
    </div>
  );
}

type Tab = "open" | "acknowledged" | "closed";
type TypeChip = "sos" | "emergency" | "device";

const TABS: { key: Tab; label: string }[] = [
  { key: "open", label: "Open" },
  { key: "acknowledged", label: "Acknowledged" },
  { key: "closed", label: "Closed" },
];
const TYPE_CHIPS: { key: TypeChip; label: string }[] = [
  { key: "sos", label: "SOS" },
  { key: "emergency", label: "Emergency" },
  { key: "device", label: "Device" },
];

const isAcknowledged = (r: Incident) => !!r.acknowledged_at || r.status === "acknowledged";

function tabOf(r: Incident): Tab {
  if (!isOpenRow(r)) return "closed";
  return isAcknowledged(r) ? "acknowledged" : "open";
}

function typeOf(r: Incident): TypeChip {
  if (isEmergency(r)) return "emergency";
  if (r.kind === "device_offline" || r.kind === "battery_low") return "device";
  return "sos";
}

/** What happened, without the client's name (the card shows it as a link). */
function whatHappenedShort(r: Incident): string {
  switch (r.kind) {
    case "sos_button":
      return "Pressed the SOS button on their wearable";
    case "fall":
      return "May have fallen — signal from the wearable";
    case "immobility":
      return "Has not moved for a long time — signal from the wearable";
    case "device_offline":
      return "Band offline";
    case "battery_low":
      return "Wearable battery is low";
    case "family_sos":
      return "Family asked for urgent help";
    case "staff_emergency": {
      const d = r.details || {};
      const by = d.reported_by_label ? `, reported by ${d.reported_by_label.toLowerCase()}` : "";
      return `Emergency: ${d.type_label || "other"}${by}`;
    }
    default:
      return r.kind_label;
  }
}

const SEVERITY_LABEL: Record<Incident["severity"], string> = { critical: "Critical", warning: "Warning", info: "Info" };

function minutesSince(r: Incident): number {
  if (isOpenRow(r) && r.minutes_open) return r.minutes_open;
  return Math.max(0, Math.round((Date.now() - new Date(r.opened_at).getTime()) / 60000));
}

/** Checklist, timeline and notes for one alert: a side panel on laptop, a full-screen sheet on phone. */
/** SOS: the care team first; the family only after a confirm and "Notify family" (owner, 29 Oct). */
function SosFamilyStep({
  incident,
  busy,
  run,
}: {
  incident: Incident;
  busy: boolean;
  run: (action: () => Promise<Incident>) => void;
}) {
  const [msg, setMsg] = useState("");
  const s = incident.sos;
  if (!s) return null;
  const open = isOpenRow(incident);
  const canAct = open && can("edit");
  const familyPressed = s.source === "family" || s.source === "elder";
  let status: string;
  if (!s.family_held) {
    status = s.family_notified_at
      ? `Family told by ${s.family_notified_by || "staff"} at ${istTime(s.family_notified_at)}`
      : "Family told";
  } else if (!open) {
    status = familyPressed ? "Family not told. Only the person who pressed it saw it was handled." : "Family not told.";
  } else if (s.can_confirm) {
    status = "Family not told yet. Check it first: is it real?";
  } else {
    status = `Confirmed by ${s.confirmed_by || "staff"}. Family not told yet.`;
  }
  return (
    <section className={`ka-sos-step${s.family_held && open ? " is-held" : ""}`} aria-label="Family">
      <p className="ka-sos-status">{status}</p>
      {canAct && s.can_confirm ? (
        <div className="ka-sos-actions">
          <button type="button" disabled={busy} onClick={() => run(() => confirmSos(incident.id))}>
            Confirm it&apos;s real
          </button>
          <button type="button" className="secondary" disabled={busy} onClick={() => run(() => falseAlarmSos(incident.id))}>
            False alarm
          </button>
        </div>
      ) : null}
      {canAct && s.can_notify_family ? (
        <form
          className="ka-note"
          onSubmit={(e) => {
            e.preventDefault();
            run(async () => {
              const updated = await notifySosFamily(incident.id, msg.trim() || undefined);
              setMsg("");
              return updated;
            });
          }}
        >
          <input
            type="text"
            maxLength={300}
            placeholder="Message to family (optional)"
            value={msg}
            onChange={(e) => setMsg(e.target.value)}
            aria-label="Message to family (optional)"
          />
          <button type="submit" disabled={busy}>
            Notify family
          </button>
        </form>
      ) : null}
    </section>
  );
}

function DetailPanel({
  incident,
  options,
  busy,
  run,
  onClose,
  onResolve,
  onEscalate,
}: {
  incident: Incident;
  options: EmergencyOptions | null;
  busy: boolean;
  run: (action: () => Promise<Incident>) => void;
  onClose: () => void;
  onResolve: () => void;
  onEscalate: () => void;
}) {
  const [note, setNote] = useState("");
  const open = isOpenRow(incident);
  const canAct = open && can("edit");
  const emergency = isEmergency(incident);
  const loaded = incident.events !== undefined;
  const name = incident.elder_name || `Client #${incident.elder_id}`;

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      // A modal on top (close / escalate) handles its own Escape.
      if (e.key === "Escape" && !document.querySelector(".home-safety-showcase-modal")) onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="ka-panel-backdrop" role="presentation" onClick={onClose}>
      <aside className="ka-panel" role="dialog" aria-modal="true" aria-label={`${incident.kind_label} — ${name}`} onClick={(e) => e.stopPropagation()}>
        <header className="ka-panel-head">
          <div className="ka-panel-title">
            <span className={`ka-sev is-${open ? incident.severity : "closed"}`}>{open ? SEVERITY_LABEL[incident.severity] : "Closed"}</span>
            <h2>
              <Link href={`/kushalaya/customers/${incident.elder_id}`}>{name}</Link>
            </h2>
            <p>{whatHappenedShort(incident)}</p>
          </div>
          <button type="button" className="ka-close" onClick={onClose} aria-label="Close panel">
            ×
          </button>
        </header>
        <div className="ka-panel-body">
          <SosFamilyStep incident={incident} busy={busy} run={run} />
          {emergency && loaded ? <EmergencyPanel incident={incident} options={options} busy={busy} run={run} /> : null}
          {incident.note ? (
            <p>
              <strong>{emergency ? "What we were told:" : "Signal:"}</strong> {incident.note}
            </p>
          ) : null}
          {incident.resolution_note ? (
            <p>
              <strong>Closing note:</strong> {incident.resolution_note}
            </p>
          ) : null}
          <h3 className="ka-panel-sub">Timeline</h3>
          <Timeline events={incident.events} />
          {canAct ? (
            <form
              className="ka-note"
              onSubmit={(e) => {
                e.preventDefault();
                const text = note.trim();
                if (!text) return;
                run(async () => {
                  const updated = await noteIncident(incident.id, text);
                  setNote("");
                  return updated;
                });
              }}
            >
              <input
                type="text"
                placeholder="Add a note (e.g. called daughter, no answer)"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                aria-label="Note"
              />
              <button type="submit" className="secondary" disabled={busy || !note.trim()}>
                Add note
              </button>
            </form>
          ) : null}
        </div>
        {canAct ? (
          <footer className="ka-panel-foot">
            <button type="button" className="secondary" disabled={busy} onClick={onEscalate}>
              Escalate…
            </button>
            <button type="button" disabled={busy} onClick={onResolve}>
              {emergency ? "Close emergency…" : "Close alert…"}
            </button>
          </footer>
        ) : null}
      </aside>
    </div>
  );
}

export default function LiveWellAlertsPage() {
  const edit = can("edit");
  const [tab, setTab] = useState<Tab>("open");
  const [type, setType] = useState<TypeChip | null>(null);
  const [active, setActive] = useState<Incident[] | null>(null);
  const [closed, setClosed] = useState<Incident[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [panelId, setPanelId] = useState<number | null>(null);
  const [details, setDetails] = useState<Record<number, Incident>>({});
  const [busyId, setBusyId] = useState<number | null>(null);
  const [resolving, setResolving] = useState<Incident | null>(null);
  const [reportFor, setReportFor] = useState<{ incident: Incident; note: string } | null>(null);
  const [escalating, setEscalating] = useState<Incident | null>(null);
  const [options, setOptions] = useState<EmergencyOptions | null>(null);

  const load = useCallback(async () => {
    try {
      const [a, c] = await Promise.all([fetchIncidents(), tab === "closed" ? fetchIncidents("resolved,closed") : Promise.resolve(null)]);
      setActive(a);
      if (c) setClosed(c);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load alerts");
    }
  }, [tab]);

  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  useEffect(() => {
    fetchEmergencyOptions().then(setOptions).catch(() => undefined);
  }, []);

  const applyUpdate = useCallback((updated: Incident) => {
    setDetails((prev) => ({ ...prev, [updated.id]: { ...prev[updated.id], ...updated } }));
    const merge = (prev: Incident[] | null) => (prev ? prev.map((r) => (r.id === updated.id ? { ...r, ...updated, events: undefined } : r)) : prev);
    setActive(merge);
    setClosed(merge);
  }, []);

  const openPanel = useCallback(async (id: number) => {
    setPanelId(id);
    try {
      const d = await fetchIncident(id);
      setDetails((prev) => ({ ...prev, [id]: d }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load alert");
    }
  }, []);

  // ?open=<id> (from "Raise emergency" on a client page) opens that alert on the tab it belongs to.
  useEffect(() => {
    const id = Number(new URLSearchParams(window.location.search).get("open"));
    if (!id) return;
    void openPanel(id);
    fetchIncident(id)
      .then((d) => setTab(tabOf(d)))
      .catch(() => undefined);
  }, [openPanel]);

  async function run(id: number, action: () => Promise<Incident>) {
    setBusyId(id);
    try {
      const updated = await action();
      applyUpdate(updated);
      setError(null);
      if (!isOpenRow(updated)) void load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusyId(null);
    }
  }

  const activeRows = active ?? [];
  const counts = {
    open: activeRows.filter((r) => tabOf(r) === "open").length,
    acknowledged: activeRows.filter((r) => tabOf(r) === "acknowledged").length,
  };
  const pool = tab === "closed" ? closed : active;
  const rows = pool === null ? null : pool.filter((r) => tabOf(r) === tab && (!type || typeOf(r) === type));
  const panelRow = panelId === null ? null : [...activeRows, ...(closed ?? [])].find((r) => r.id === panelId);
  const panelIncident = panelId === null ? null : details[panelId] ? { ...panelRow, ...details[panelId] } : panelRow;

  let empty = "";
  if (rows && rows.length === 0) {
    const what = type ? `${TYPE_CHIPS.find((t) => t.key === type)!.label} ` : "";
    if (tab === "open") empty = `No open ${what}alerts — nothing is waiting for someone to pick it up.`;
    else if (tab === "acknowledged") empty = `No acknowledged ${what}alerts still in progress.`;
    else empty = `No closed ${what}alerts yet.`;
  }

  return (
    <>
      <div className="ks-head-row">
        <PageHeader title="SOS & alerts" subtitle="Acknowledge within 5 minutes, or it goes to the whole team" />
        <div className="ks-head-actions">
          {edit ? (
            <RaiseEmergencyButton
              onRaised={(row) => {
                setTab(tabOf(row));
                void load();
                void openPanel(row.id);
              }}
            >
              <span className="ks-ha-icon" aria-hidden="true">!</span>
              <span className="ks-ha-label">Raise emergency</span>
            </RaiseEmergencyButton>
          ) : null}
          <button type="button" className="secondary" onClick={() => void load()} aria-label="Refresh" title="Refresh">
            <span className="ks-ha-icon" aria-hidden="true">↻</span>
            <span className="ks-ha-label">Refresh</span>
          </button>
        </div>
      </div>
      <SmsOffBanner />

      <div className="ka-filters">
        <div className="tabs ks-ltabs ka-tabs" role="tablist" aria-label="Alert status">
          {TABS.map((t) => {
            const n = t.key === "closed" ? 0 : counts[t.key];
            return (
              <button
                key={t.key}
                type="button"
                role="tab"
                aria-selected={tab === t.key}
                className={`tab${tab === t.key ? " active" : ""}`}
                onClick={() => setTab(t.key)}
              >
                {t.label}
                {n ? <span className={`ka-count${t.key === "open" ? " is-hot" : ""}`}>{n}</span> : null}
              </button>
            );
          })}
        </div>
        <div className="ka-chips" aria-label="Type">
          {TYPE_CHIPS.map((c) => (
            <button
              key={c.key}
              type="button"
              className={`ka-chip${type === c.key ? " is-on" : ""}`}
              aria-pressed={type === c.key}
              onClick={() => setType(type === c.key ? null : c.key)}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      {error ? <p className="error">{error}</p> : null}

      {rows === null ? (
        <p className="muted">Loading…</p>
      ) : empty ? (
        <div className="ka-empty">
          <p>{empty}</p>
          {tab === "open" && counts.acknowledged ? (
            <button type="button" className="secondary" onClick={() => setTab("acknowledged")}>
              See {counts.acknowledged} acknowledged
            </button>
          ) : null}
        </div>
      ) : (
        <ul className="ka-list">
          {rows.map((r) => {
            const open = isOpenRow(r);
            const busy = busyId === r.id;
            const merged = details[r.id] ? { ...r, ...details[r.id] } : r;
            const name = r.elder_name || `Client #${r.elder_id}`;
            return (
              <li key={r.id} className={`ka-card is-${open ? r.severity : "closed"}`}>
                <div className="ka-card-top">
                  <span className={`ka-sev is-${open ? r.severity : "closed"}`}>{open ? SEVERITY_LABEL[r.severity] : "Closed"}</span>
                  <span className="ka-kind">{r.kind_label}</span>
                  <span className="ka-when" title={formatIST(r.opened_at)}>
                    {ago(minutesSince(r))}
                  </span>
                </div>
                <h2 className="ka-client">
                  <Link href={`/kushalaya/customers/${r.elder_id}`}>{name}</Link>
                </h2>
                <p className="ka-what">{whatHappenedShort(r)}</p>
                <p className={`ka-status${open && !isAcknowledged(r) && !isEmergency(r) ? " is-waiting" : ""}`}>{whereItStands(r)}</p>
                {r.elder_address ? <p className="ka-address">{r.elder_address}</p> : null}
                <div className="ka-actions">
                  {edit && open && !r.acknowledged_at ? (
                    <button type="button" className="ka-ack" disabled={busy} onClick={() => void run(r.id, () => acknowledgeIncident(r.id))}>
                      Acknowledge
                    </button>
                  ) : null}
                  {r.elder_phone ? (
                    <a className="ks-call-btn" href={`tel:${r.elder_phone}`} title={r.elder_phone}>
                      <PhoneIcon />
                      Call client
                    </a>
                  ) : null}
                  {r.family_phone ? (
                    <a className="ks-call-btn" href={`tel:${r.family_phone}`} title={`${r.family_name ? `${r.family_name} · ` : ""}${r.family_phone}`}>
                      <PhoneIcon />
                      Call family{r.family_name ? ` (${r.family_name.split(" ")[0]})` : ""}
                    </a>
                  ) : null}
                  <Directions home={r.elder_home} address={r.elder_address} name={r.elder_name ?? undefined} summaryClassName="ks-call-btn" />
                  <button type="button" className="secondary" aria-haspopup="dialog" onClick={() => void openPanel(r.id)}>
                    {isEmergency(r) ? "Checklist & timeline" : "Timeline"}
                  </button>
                  {edit && open ? (
                    <button type="button" className="secondary" disabled={busy} onClick={() => setResolving(merged)}>
                      {isEmergency(r) ? "Close emergency…" : "Resolve…"}
                    </button>
                  ) : null}
                  {edit && open ? (
                    <button type="button" className="secondary ka-escalate" disabled={busy} onClick={() => setEscalating(r)}>
                      Escalate…
                    </button>
                  ) : null}
                </div>
                {open && (!r.elder_phone || !r.family_phone) ? (
                  <p className="ka-missing">
                    {!r.elder_phone ? "No client phone on file" : ""}
                    {!r.elder_phone && !r.family_phone ? " · " : ""}
                    {!r.family_phone ? "No family phone on file" : ""}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}

      {panelIncident ? (
        <DetailPanel
          incident={panelIncident}
          options={options}
          busy={busyId === panelIncident.id}
          run={(a) => void run(panelIncident.id, a)}
          onClose={() => setPanelId(null)}
          onResolve={() => setResolving(panelIncident)}
          onEscalate={() => setEscalating(panelIncident)}
        />
      ) : null}

      {resolving ? (
        <ResolveModal
          incident={resolving}
          options={options}
          busy={busyId === resolving.id}
          onClose={() => setResolving(null)}
          onSubmit={(outcome, note) => {
            const target = resolving;
            void run(target.id, async () => {
              const updated = isEmergency(target)
                ? await closeEmergency(target.id, outcome, note)
                : await resolveIncident(target.id, outcome as IncidentOutcome, note);
              setResolving(null);
              if (outcome === "hospital_admission") setReportFor({ incident: target, note });
              return updated;
            });
          }}
        />
      ) : null}

      {reportFor ? (
        <Modal title="File an incident report?" onClose={() => setReportFor(null)}>
          <p style={{ marginTop: 0 }}>
            {reportFor.incident.elder_name || "The client"} was admitted to hospital. A hospital admission needs an incident
            report — it opens on the client&apos;s Incidents tab, already filled in from this emergency.
          </p>
          <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end", flexWrap: "wrap" }}>
            <button type="button" className="secondary" onClick={() => setReportFor(null)}>
              Later
            </button>
            <button
              type="button"
              onClick={() => {
                startIncidentReport(reportFor.incident, reportFor.note);
                window.location.href = `/kushalaya/customers/${reportFor.incident.elder_id}?tab=incidents`;
              }}
            >
              Start incident report
            </button>
          </div>
        </Modal>
      ) : null}

      {escalating ? (
        <ConfirmEscalate
          incident={escalating}
          busy={busyId === escalating.id}
          onClose={() => setEscalating(null)}
          onConfirm={() => {
            const target = escalating;
            void run(target.id, async () => {
              const updated = await escalateIncident(target.id);
              setEscalating(null);
              return updated;
            });
          }}
        />
      ) : null}
    </>
  );
}
