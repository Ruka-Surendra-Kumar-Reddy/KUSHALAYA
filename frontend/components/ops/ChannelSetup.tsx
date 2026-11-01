"use client";

import { FormEvent, useEffect, useState } from "react";
import { api } from "@/lib/api";

type EmailCfg = {
  host: string;
  port: number;
  username: string;
  from_email: string;
  from_name: string;
  enabled: boolean;
  secret_set: boolean;
  env_configured: boolean;
  updated_by: string;
};
type SmsCfg = {
  sender_id: string;
  template_id: string;
  route: string;
  enabled: boolean;
  secret_set: boolean;
  env_configured: boolean;
  updated_by: string;
};

const ZOHO_HOSTS = [
  { host: "smtp.zoho.in", label: "Zoho India (zoho.in)" },
  { host: "smtp.zoho.com", label: "Zoho global (zoho.com)" },
  { host: "smtppro.zoho.in", label: "Zoho India — own domain (smtppro.zoho.in)" },
  { host: "smtppro.zoho.com", label: "Zoho global — own domain (smtppro.zoho.com)" },
];

function errText(e: unknown) {
  return e instanceof Error ? e.message : String(e);
}

/** Settings → Email notifications: connect Zoho Mail (SMTP) and MSG91 (SMS). Admins only. */
export function ChannelSetup({ defaultEmail, onChange }: { defaultEmail: string; onChange?: () => void }) {
  const [email, setEmail] = useState<EmailCfg | null>(null);
  const [sms, setSms] = useState<SmsCfg | null>(null);
  const [open, setOpen] = useState<"email" | "sms" | null>(null);
  const [password, setPassword] = useState("");
  const [authKey, setAuthKey] = useState("");
  const [testTo, setTestTo] = useState(defaultEmail);
  const [testPhone, setTestPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<{ kind: "email" | "sms"; ok: boolean; text: string } | null>(null);

  useEffect(() => {
    api<{ email: EmailCfg; sms: SmsCfg }>("/api/v1/team/channels")
      .then((d) => {
        setEmail(d.email);
        setSms(d.sms);
      })
      .catch(() => undefined);
  }, []);

  async function saveEmail(e: FormEvent, enable = true) {
    e.preventDefault();
    if (!email) return;
    setBusy(true);
    setNote(null);
    try {
      const saved = await api<EmailCfg>("/api/v1/team/channels/email", {
        method: "PUT",
        body: JSON.stringify({ ...email, password: password || undefined, enabled: enable }),
      });
      setEmail(saved);
      setPassword("");
      // Prove it works straight away.
      const r = await api<{ ok: boolean; detail: string }>("/api/v1/team/email-notifications/test", {
        method: "POST",
        body: JSON.stringify({ to: testTo || saved.username }),
      });
      setNote({
        kind: "email",
        ok: r.ok,
        text: r.ok
          ? `Saved and connected. A test email went to ${testTo || saved.username}.`
          : `Saved, but the test failed: ${r.detail || "check the email and app password"}.`,
      });
      if (r.ok) setOpen(null);
      onChange?.();
    } catch (err) {
      setNote({ kind: "email", ok: false, text: errText(err) });
    } finally {
      setBusy(false);
    }
  }

  async function turnOff(kind: "email" | "sms") {
    setBusy(true);
    try {
      const saved = await api<EmailCfg & SmsCfg>(`/api/v1/team/channels/${kind}`, {
        method: "PUT",
        body: JSON.stringify({ enabled: false }),
      });
      if (kind === "email") setEmail(saved);
      else setSms(saved);
      setNote({ kind, ok: true, text: "Turned off." });
      onChange?.();
    } catch (err) {
      setNote({ kind, ok: false, text: errText(err) });
    } finally {
      setBusy(false);
    }
  }

  async function saveSms(e: FormEvent) {
    e.preventDefault();
    if (!sms) return;
    setBusy(true);
    setNote(null);
    try {
      const saved = await api<SmsCfg>("/api/v1/team/channels/sms", {
        method: "PUT",
        body: JSON.stringify({ ...sms, sender_id: sms.sender_id.toUpperCase(), auth_key: authKey || undefined, enabled: true }),
      });
      setSms(saved);
      setAuthKey("");
      if (testPhone) {
        const r = await api<{ ok: boolean; detail: string }>("/api/v1/team/channels/sms/test", {
          method: "POST",
          body: JSON.stringify({ to: testPhone }),
        });
        setNote({
          kind: "sms",
          ok: r.ok,
          text: r.ok ? `Saved. A test SMS went to ${testPhone}.` : `Saved, but the test failed: ${r.detail}`,
        });
      } else {
        setNote({ kind: "sms", ok: true, text: "Saved and switched on." });
      }
      setOpen(null);
    } catch (err) {
      setNote({ kind: "sms", ok: false, text: errText(err) });
    } finally {
      setBusy(false);
    }
  }

  if (!email || !sms) return null;

  const emailOn = email.enabled && email.secret_set;
  const smsOn = sms.enabled && sms.secret_set;
  const zohoPreset = ZOHO_HOSTS.some((z) => z.host === email.host);

  return (
    <section className="card nt-channels" aria-labelledby="nt-channels-title">
      <h2 id="nt-channels-title">Connections</h2>
      <p className="muted">The accounts that send your emails and SMS. Passwords are stored encrypted and never shown again.</p>

      <div className={`nt-channel${emailOn ? " is-on" : ""}`}>
        <div className="nt-channel-head">
          <span className="nt-channel-ico" aria-hidden="true">✉</span>
          <div>
            <strong>Email — Zoho Mail</strong>
            <small>
              {emailOn
                ? `Connected · sending as ${email.from_email || email.username}`
                : email.env_configured
                  ? "Using the server’s built-in setup"
                  : "Not connected — emails are recorded, not sent"}
            </small>
          </div>
          <span className={`nt-pill${emailOn ? " is-on" : ""}`}>{emailOn ? "On" : "Off"}</span>
          <button type="button" className="nt-link" onClick={() => setOpen(open === "email" ? null : "email")}>
            {open === "email" ? "Close" : emailOn ? "Edit" : "Set up"}
          </button>
        </div>
        {note?.kind === "email" && <p className={`nt-note${note.ok ? " is-ok" : " is-bad"}`}>{note.text}</p>}
        {open === "email" && (
          <form className="nt-form" onSubmit={(e) => void saveEmail(e)}>
            <ol className="nt-steps">
              <li>
                Sign in to <b>Zoho Mail</b> → your profile → <b>My Account</b> → <b>Security</b> →{" "}
                <b>App passwords</b> → <b>Generate</b> (name it “KushAlaya”).
              </li>
              <li>Paste that app password below with the Zoho email address. Then save — we send you a test.</li>
            </ol>
            <label>
              Zoho email address
              <input
                type="email"
                required
                value={email.username}
                placeholder="care@kushalaya.com"
                onChange={(e) => setEmail({ ...email, username: e.target.value })}
              />
            </label>
            <label>
              App password
              <input
                type="password"
                autoComplete="new-password"
                required={!email.secret_set}
                value={password}
                placeholder={email.secret_set ? "Saved — leave blank to keep it" : "xxxx xxxx xxxx"}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <label>
              Zoho account
              <select
                value={zohoPreset ? email.host : "other"}
                onChange={(e) => setEmail({ ...email, host: e.target.value === "other" ? "" : e.target.value })}
              >
                {ZOHO_HOSTS.map((z) => (
                  <option key={z.host} value={z.host}>
                    {z.label}
                  </option>
                ))}
                <option value="other">Other mail server…</option>
              </select>
            </label>
            {!zohoPreset && (
              <label>
                Mail server (SMTP host)
                <input required value={email.host} onChange={(e) => setEmail({ ...email, host: e.target.value })} />
              </label>
            )}
            <label>
              Sender name
              <input value={email.from_name} onChange={(e) => setEmail({ ...email, from_name: e.target.value })} />
            </label>
            <label>
              Send test to
              <input type="email" value={testTo} onChange={(e) => setTestTo(e.target.value)} />
            </label>
            <details className="nt-advanced">
              <summary>Advanced</summary>
              <label>
                Port
                <select value={email.port} onChange={(e) => setEmail({ ...email, port: Number(e.target.value) })}>
                  <option value={587}>587 — TLS (recommended)</option>
                  <option value={465}>465 — SSL</option>
                </select>
              </label>
              <label>
                “From” address (if different)
                <input
                  type="email"
                  value={email.from_email}
                  placeholder={email.username}
                  onChange={(e) => setEmail({ ...email, from_email: e.target.value })}
                />
              </label>
            </details>
            <div className="nt-form-actions">
              {emailOn && (
                <button type="button" className="nt-link is-danger" disabled={busy} onClick={() => void turnOff("email")}>
                  Turn off
                </button>
              )}
              <button type="submit" disabled={busy}>
                {busy ? "Saving and testing…" : "Save and send test"}
              </button>
            </div>
          </form>
        )}
      </div>

      <div className={`nt-channel${smsOn ? " is-on" : ""}`}>
        <div className="nt-channel-head">
          <span className="nt-channel-ico" aria-hidden="true">✆</span>
          <div>
            <strong>SMS — MSG91</strong>
            <small>
              {smsOn
                ? `Connected · sender ${sms.sender_id}`
                : sms.env_configured
                  ? "Using the server’s built-in setup"
                  : "Not connected — SMS are recorded, not sent"}
            </small>
          </div>
          <span className={`nt-pill${smsOn ? " is-on" : ""}`}>{smsOn ? "On" : "Off"}</span>
          <button type="button" className="nt-link" onClick={() => setOpen(open === "sms" ? null : "sms")}>
            {open === "sms" ? "Close" : smsOn ? "Edit" : "Set up"}
          </button>
        </div>
        {note?.kind === "sms" && <p className={`nt-note${note.ok ? " is-ok" : " is-bad"}`}>{note.text}</p>}
        {open === "sms" && (
          <form className="nt-form" onSubmit={(e) => void saveSms(e)}>
            <ol className="nt-steps">
              <li>
                In <b>MSG91</b>: copy your <b>Auth key</b> (profile menu → Authkey).
              </li>
              <li>
                Use your DLT-approved <b>Sender ID</b> (6 letters) and <b>DLT template ID</b>. In India an SMS is
                delivered only when its text matches an approved template.
              </li>
            </ol>
            <label>
              Auth key
              <input
                type="password"
                autoComplete="new-password"
                required={!sms.secret_set}
                value={authKey}
                placeholder={sms.secret_set ? "Saved — leave blank to keep it" : "Paste the MSG91 auth key"}
                onChange={(e) => setAuthKey(e.target.value)}
              />
            </label>
            <label>
              Sender ID
              <input
                required
                maxLength={6}
                minLength={6}
                value={sms.sender_id}
                placeholder="KUSHAL"
                onChange={(e) => setSms({ ...sms, sender_id: e.target.value.toUpperCase() })}
              />
            </label>
            <label>
              DLT template ID
              <input value={sms.template_id} onChange={(e) => setSms({ ...sms, template_id: e.target.value })} />
            </label>
            <label>
              Send a test SMS to (optional)
              <input type="tel" value={testPhone} placeholder="98xxxxxxxx" onChange={(e) => setTestPhone(e.target.value)} />
            </label>
            <div className="nt-form-actions">
              {smsOn && (
                <button type="button" className="nt-link is-danger" disabled={busy} onClick={() => void turnOff("sms")}>
                  Turn off
                </button>
              )}
              <button type="submit" disabled={busy}>
                {busy ? "Saving…" : "Save"}
              </button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}
