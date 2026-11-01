"use client";

import { useEffect, useState } from "react";
import { BackLink } from "@/components/ops/PageActions";
import { api, getStoredAuth } from "@/lib/api";
import { canManageUsers } from "@/lib/auth";
import { EmailChips } from "@/components/EmailChips";
import { Flash } from "@/components/Flash";
import { ChannelSetup } from "@/components/ops/ChannelSetup";
import { EscalationTree } from "@/components/ops/EscalationTree";
import { EmergencyPartners } from "@/components/ops/EmergencyPartners";
import "@/components/ops/notifications.css";

type StaffRule = { enabled: boolean; manager: boolean; admins: boolean; extra: string[] };
type Settings = {
  staff: Record<string, StaffRule>;
  family: Record<string, boolean>;
  staff_events: { key: string; label: string }[];
  family_events: { key: string; label: string }[];
  status: { provider: string; connected: boolean; from_email: string };
};

/** Safety alerts always reach managers and admins; only extra people can be added. */
const ALWAYS_ON = "alert";

/** Settings → Email notifications: who gets which email, in one place. */
export default function EmailNotificationsPage() {
  const auth = getStoredAuth();
  const isAdmin = canManageUsers(auth?.role || "");
  const [data, setData] = useState<Settings | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    api<Settings>("/api/v1/team/email-notifications")
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  async function save(body: Partial<Pick<Settings, "staff" | "family">>, note: string) {
    try {
      setData(await api<Settings>("/api/v1/team/email-notifications", { method: "PUT", body: JSON.stringify(body) }));
      setMessage(note);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    }
  }

  function setRule(key: string, patch: Partial<StaffRule>, note: string) {
    if (!data) return;
    setData({ ...data, staff: { ...data.staff, [key]: { ...data.staff[key], ...patch } } });
    void save({ staff: { [key]: { ...data.staff[key], ...patch } } }, note);
  }

  return (
    <div className="ks-frame is-narrow">
      <header className="ks-head">
        <BackLink href="/settings" label="Settings" />
        <h1>Notifications &amp; SOS</h1>
        <p className="muted">Who gets emails and SMS for each event, and who is called in an SOS. Everything also shows on the dashboard.</p>
      </header>
      <Flash error={error} message={message} onClear={() => { setError(""); setMessage(""); }} />
      {!isAdmin && (
        <p className="card st-viewonly" role="note">
          <strong>View only.</strong> This is who is told about what.
        </p>
      )}

      {!data ? (
        <p className="muted">Loading…</p>
      ) : (
        <>
          {isAdmin ? (
            <ChannelSetup defaultEmail={auth?.email || ""} />
          ) : (
            <section className={`card nt-status${data.status.connected ? " is-on" : ""}`}>
              <strong>{data.status.connected ? "Email is connected." : "Email is not connected yet."}</strong>{" "}
              <span className="muted">
                {data.status.connected
                  ? "The emails below are being sent."
                  : "The emails below go out once an admin connects email here."}
              </span>
            </section>
          )}

          <section className="card">
            <h2>Emails to your team</h2>
            <ul className="nt-rules">
              {data.staff_events.map((ev) => {
                const r = data.staff[ev.key];
                const fixed = ev.key === ALWAYS_ON;
                return (
                  <li key={ev.key} className={r.enabled || fixed ? "" : "is-off"}>
                    <div className="nt-rule-head ks-switches">
                      <label>
                        <input
                          type="checkbox"
                          role="switch"
                          checked={fixed || r.enabled}
                          disabled={!isAdmin || fixed}
                          onChange={(e) =>
                            setRule(ev.key, { enabled: e.target.checked }, `${ev.label}: ${e.target.checked ? "on" : "off"}.`)
                          }
                        />
                        <span>{ev.label}</span>
                      </label>
                      {fixed && <small>Always on for safety</small>}
                    </div>
                    {(r.enabled || fixed) && (
                      <div className="nt-who">
                        <span className="nt-who-label">Send to</span>
                        <label className="nt-check">
                          <input
                            type="checkbox"
                            checked={fixed || r.manager}
                            disabled={!isAdmin || fixed}
                            onChange={(e) => setRule(ev.key, { manager: e.target.checked }, "Saved.")}
                          />
                          The client’s care manager
                        </label>
                        <label className="nt-check">
                          <input
                            type="checkbox"
                            checked={fixed || r.admins}
                            disabled={!isAdmin || fixed}
                            onChange={(e) => setRule(ev.key, { admins: e.target.checked }, "Saved.")}
                          />
                          All admins
                        </label>
                        <div className="nt-extra">
                          <span className="nt-who-label">Also send to</span>
                          <EmailChips
                            value={r.extra}
                            disabled={!isAdmin}
                            onChange={(extra) => setRule(ev.key, { extra }, "Recipients updated.")}
                            label={`Add an email for: ${ev.label}`}
                          />
                        </div>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
            <p className="muted nt-foot">A client with no care manager: their emails go to the admins instead, so nothing is missed.</p>
          </section>

          <EscalationTree canEdit={isAdmin} />
          <EmergencyPartners canEdit={isAdmin} />

          <CareTeamContactCard canEdit={isAdmin} />

          <section className="card">
            <h2>Emails to families</h2>
            <p className="muted">
              Families get these at their sign-in email and any extra addresses they add. Each family can also turn
              them off for themselves under Notifications in the family portal.
            </p>
            <ul className="ks-switches">
              {data.family_events.map((ev) => (
                <li key={ev.key}>
                  <label>
                    <input
                      type="checkbox"
                      role="switch"
                      checked={data.family[ev.key]}
                      disabled={!isAdmin}
                      onChange={(e) =>
                        save({ family: { [ev.key]: e.target.checked } }, `${ev.label}: ${e.target.checked ? "on" : "off"}.`)
                      }
                    />
                    <span>{ev.label}</span>
                  </label>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}

type CareContact = { phone: string; whatsapp: string; is_default?: boolean };

/** Phone + WhatsApp families see on Home, Alerts and the family header. */
function CareTeamContactCard({ canEdit }: { canEdit: boolean }) {
  const [form, setForm] = useState<CareContact | null>(null);
  const [status, setStatus] = useState("");

  useEffect(() => {
    api<CareContact>("/api/v1/team/care-team-contact")
      .then(setForm)
      .catch(() => setStatus("Could not load"));
  }, []);

  async function save() {
    if (!form) return;
    setStatus("Saving…");
    try {
      setForm(
        await api<CareContact>("/api/v1/team/care-team-contact", {
          method: "PUT",
          body: JSON.stringify({ phone: form.phone, whatsapp: form.whatsapp }),
        }),
      );
      setStatus("Saved. Families see the new numbers on their next page load.");
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Could not save");
    }
  }

  return (
    <section className="card">
      <h2>Care team contact for families</h2>
      <p className="muted">
        The Call and WhatsApp buttons in the family portal use these numbers. Include the country code.
        {form?.is_default ? " Using the default number until you save your own." : ""}
      </p>
      {form ? (
        <div style={{ display: "grid", gap: "0.6rem", maxWidth: "26rem" }}>
          <label>
            Care team phone
            <input
              type="tel"
              value={form.phone}
              disabled={!canEdit}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
            />
          </label>
          <label>
            WhatsApp number
            <input
              type="tel"
              value={form.whatsapp}
              disabled={!canEdit}
              onChange={(e) => setForm({ ...form, whatsapp: e.target.value })}
            />
          </label>
          {canEdit ? (
            <button type="button" onClick={() => void save()} style={{ justifySelf: "start" }}>
              Save numbers
            </button>
          ) : null}
        </div>
      ) : null}
      {status ? <p className="muted">{status}</p> : null}
    </section>
  );
}
