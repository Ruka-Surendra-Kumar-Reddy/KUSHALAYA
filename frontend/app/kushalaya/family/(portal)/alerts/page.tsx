"use client";

import { withPublicBrand } from "@/lib/public-brand";
import { familyTime } from "@/lib/livewell/familyTime";
import { useFamilyTimezone } from "@/lib/family-zone";

import { useEffect, useState } from "react";
import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import { FamilyLink as Link } from "@/components/livewell/family/FamilyLink";
import { FamilyError } from "@/components/livewell/family/FamilyError";
import { CareTeamButtons, EmergencyNumbers } from "@/components/livewell/family/CareTeamContact";
import { FamilyConfirmSheet } from "@/components/livewell/family/FamilyConfirmSheet";
import {
  fetchFamilyAlerts,
  fetchFamilyDashboard,
  fetchFamilyIncidents,
  markFamilyAlertRead,
  resolveFamilyIncident,
  sendFamilySos,
  type CareTeamContact,
  type FamilyAlert,
  type FamilyIncident,
} from "@/lib/livewell/familyApi";

function isOpenStatus(status: string) {
  const s = (status || "open").toLowerCase();
  return s !== "closed" && s !== "resolved";
}

/** Plain words for the family: what is happening with their SOS. */
const SOS_STATUS: Record<string, string> = {
  open: "Sent — your care team has been alerted",
  acknowledged: "Care team is on it",
  escalated: "Senior care team alerted",
  resolved: "Closed",
  closed: "Closed",
};

export default function FamilyAlertsPage() {
  const tz = useFamilyTimezone();
  const [items, setItems] = useState<FamilyAlert[]>([]);
  const [contact, setContact] = useState<CareTeamContact | null>(null);
  const [incidents, setIncidents] = useState<FamilyIncident[]>([]);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [sosNote, setSosNote] = useState("");
  const [sosBusy, setSosBusy] = useState(false);
  const [sosMsg, setSosMsg] = useState("");
  const [resolveBusyId, setResolveBusyId] = useState<string | null>(null);
  // In-app confirm sheets (no native confirm()).
  const [confirmSos, setConfirmSos] = useState(false);
  const [confirmClose, setConfirmClose] = useState<string | null>(null);

  async function load() {
    const [alerts, inc] = await Promise.all([fetchFamilyAlerts(), fetchFamilyIncidents()]);
    setItems(alerts);
    setIncidents(inc);
  }

  function reload() {
    setError("");
    load().catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }

  useEffect(() => {
    reload();
    // Care team number for the call bar; the defaults show until it answers.
    fetchFamilyDashboard()
      .then((d) => setContact(d.care_team_contact ?? null))
      .catch(() => undefined);
  }, []);

  async function markRead(id: string) {
    try {
      await markFamilyAlertRead(id);
      // Reading an alert does not close an SOS — only the care team (or "We're OK — cancel SOS") does.
      await load();
    } catch {
      setActionError("We couldn't mark that alert as read. Please try again.");
    }
  }

  async function onResolve(id: string) {
    setConfirmClose(null);
    setResolveBusyId(id);
    setActionError("");
    try {
      await resolveFamilyIncident(id, "resolved");
      setSosMsg("SOS closed. We've told your care team everyone is safe.");
      await load();
    } catch {
      setActionError("We couldn't close the SOS. Please call the care team instead.");
    } finally {
      setResolveBusyId(null);
    }
  }

  async function onSos() {
    setConfirmSos(false);
    setSosBusy(true);
    setSosMsg("");
    setActionError("");
    try {
      await sendFamilySos(sosNote.trim() || undefined);
      setSosNote("");
      setSosMsg("SOS sent. Your care team has been alerted.");
      await load();
    } catch {
      setActionError("The SOS did not go through. Please call the care team or 112 now.");
    } finally {
      setSosBusy(false);
    }
  }

  const openAlerts = items.filter((n) => !n.read_at);
  const pastAlerts = items.filter((n) => n.read_at);
  const sosIncidents = incidents
    .filter((i) => i.kind === "sos")
    .sort((a, b) => Number(isOpenStatus(b.status)) - Number(isOpenStatus(a.status)))
    .slice(0, 8);
  const openSos = sosIncidents.filter((i) => isOpenStatus(i.status));
  // Emergencies the care team raised: a plain status only, closed by the team.
  const emergencies = incidents.filter((i) => i.kind === "emergency").slice(0, 3);

  return (
    <FamilyShell title="Alerts & SOS" subtitle="Urgent notices and help requests">
      <section className="fh-alerts-callbar" aria-labelledby="fh-callbar-h">
        <h2 id="fh-callbar-h">Talk to the care team now</h2>
        <CareTeamButtons contact={contact} />
        <EmergencyNumbers contact={contact} />
      </section>

      <FamilyError message={error} onRetry={reload} what="your alerts" />
      {actionError ? <p className="error-text">{actionError}</p> : null}
      {sosMsg ? <p className="home-safety-family-success">{sosMsg}</p> : null}

      {emergencies.length ? (
        <section className="card home-safety-section" aria-labelledby="fh-emg-status-h">
          <h2 id="fh-emg-status-h">
            {emergencies.some((i) => isOpenStatus(i.status)) ? "Emergency in progress" : "Recent emergencies"}
          </h2>
          <ul style={{ listStyle: "none", margin: "0 0 0.75rem", padding: 0 }}>
            {emergencies.map((i) => (
              <li key={i.id} style={{ padding: "0.35rem 0" }}>
                <span>{i.note}</span>{" "}
                <span className="muted">
                  · {familyTime(i.created_at, tz)}
                  {isOpenStatus(i.status) ? "" : " · closed"}
                </span>
              </li>
            ))}
          </ul>
          {emergencies.some((i) => isOpenStatus(i.status)) ? (
            <>
              <p className="muted" style={{ marginTop: 0 }}>
                The care team is handling this. Call them any time for an update.
              </p>
              <CareTeamButtons contact={contact} compact />
            </>
          ) : null}
        </section>
      ) : null}

      <section id="sos" className="card home-safety-section home-safety-family-sos">
        <h2>Need urgent help?</h2>
        <p className="muted">
          {withPublicBrand("Sends an urgent alert to the LiveWell360 care team. If it is life-threatening, call 112 or 108 first.")}
        </p>
        <label className="home-safety-field">
          Optional note
          <input
            value={sosNote}
            onChange={(e) => setSosNote(e.target.value)}
            placeholder="e.g. Fall suspected — please call"
          />
        </label>
        <button type="button" className="danger primary" onClick={() => setConfirmSos(true)} disabled={sosBusy}>
          {sosBusy ? "Sending…" : "Send SOS"}
        </button>
        {sosIncidents.length > 0 ? (
          <div className="home-safety-family-sos-history">
            <h3>Recent SOS{openSos.length ? ` · ${openSos.length} open` : ""}</h3>
            <ul>
              {sosIncidents.map((i) => {
                const open = isOpenStatus(i.status);
                const days = open && i.created_at
                  ? Math.floor((Date.now() - new Date(i.created_at).getTime()) / 86400000)
                  : 0;
                return (
                  <li key={i.id}>
                    <strong>{SOS_STATUS[String(i.status || "").toLowerCase()] ?? i.status}</strong>
                    {i.note ? ` · ${i.note}` : ""} <span className="muted">{familyTime(i.created_at, tz)}</span>
                    {open ? (
                      <>
                        {" "}
                        <button
                          type="button"
                          className="secondary fh-sos-close"
                          disabled={resolveBusyId === i.id}
                          onClick={() => setConfirmClose(i.id)}
                        >
                          {resolveBusyId === i.id ? "Closing…" : "We're safe — close SOS"}
                        </button>
                        {days >= 1 ? (
                          <>
                            <p className="error-text" style={{ marginTop: "0.5rem" }}>
                              Open for {days} day{days === 1 ? "" : "s"} — call the care team.
                            </p>
                            <CareTeamButtons contact={contact} compact />
                          </>
                        ) : null}
                      </>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null}
      </section>

      <section className="home-safety-family-p0-section">
        <h2 className="home-safety-family-p0-heading">New alerts</h2>
        {openAlerts.length === 0 ? (
          <div className="card home-safety-empty">
            <p>{items.length === 0 ? "No alerts yet." : "You're all caught up. No new alerts."}</p>
          </div>
        ) : (
          <ul className="home-safety-family-alert-list">
            {openAlerts.map((n) => (
              <li
                key={n.id}
                className={`card home-safety-family-alert${
                  n.severity === "critical" ? " is-critical" : ""
                }`}
              >
                <strong>{n.title}</strong>
                <span className="home-safety-draft-badge">New</span>
                <p>{n.body}</p>
                <p className="muted" style={{ fontSize: "0.8rem" }}>
                  {familyTime(n.created_at, tz)}
                </p>
                <button type="button" className="secondary" onClick={() => void markRead(n.id)}>
                  Mark as read
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {pastAlerts.length > 0 ? (
        <details className="fh-past-alerts">
          <summary>
            <span>Show past alerts ({pastAlerts.length})</span>
            <span className="fh-switch" aria-hidden="true" />
          </summary>
          <ul className="home-safety-family-alert-list">
            {pastAlerts.map((n) => (
              <li key={n.id} className="card home-safety-family-alert">
                <strong>{n.title}</strong>
                <p>{n.body}</p>
                <p className="muted" style={{ fontSize: "0.8rem" }}>
                  {familyTime(n.created_at, tz)}
                </p>
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      <p className="muted">
        <Link href="/kushalaya/family/contacts" className="fh-tap">Local emergency contacts →</Link>
      </p>

      <FamilyConfirmSheet
        open={confirmSos}
        danger
        title="Send an SOS now?"
        confirmLabel="Yes, send SOS"
        cancelLabel="Don't send"
        busy={sosBusy}
        onConfirm={() => void onSos()}
        onCancel={() => setConfirmSos(false)}
      >
        <p>{withPublicBrand("Your LiveWell360 care team is alerted straight away.")}</p>
        <p>If it is life-threatening, call 112 or 108 first.</p>
      </FamilyConfirmSheet>
      <FamilyConfirmSheet
        open={!!confirmClose}
        title="Is everyone safe?"
        confirmLabel="Yes, close the SOS"
        cancelLabel="Keep it open"
        busy={!!confirmClose && resolveBusyId === confirmClose}
        onConfirm={() => confirmClose && void onResolve(confirmClose)}
        onCancel={() => setConfirmClose(null)}
      >
        <p>Close the SOS only if everyone is safe. We&rsquo;ll let your care team know.</p>
      </FamilyConfirmSheet>
    </FamilyShell>
  );
}
