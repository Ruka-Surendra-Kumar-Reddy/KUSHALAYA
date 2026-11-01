"use client";

import { useCallback, useEffect, useState } from "react";
import { getApiUrl } from "@/lib/api";
import { PublicBrandMark } from "@/components/BrandLogo";
import { portalFont } from "@/components/portal-font";
import { formatIST } from "@/lib/ist";
import "../../../login/login.css";

type View = {
  partner_name: string;
  expired: boolean;
  closed: boolean;
  last_status: string | null;
  statuses: { value: string; label: string }[];
  client_name: string | null;
  address: string | null;
  client_phone: string | null;
  what_happened: string | null;
  opened_at: string | null;
  care_team_phone?: string;
  care_team_tel?: string;
};

type Contact = { phone: string; tel: string };

function contactFrom(data: { care_team_phone?: unknown; care_team_tel?: unknown }): Contact | null {
  return typeof data.care_team_phone === "string" && typeof data.care_team_tel === "string"
    ? { phone: data.care_team_phone, tel: data.care_team_tel }
    : null;
}

export default function PartnerResponse({ incidentId, token }: { incidentId: string; token: string }) {
  const url = `${getApiUrl()}/api/v1/home-safety/emergency-response/${encodeURIComponent(incidentId)}/${encodeURIComponent(token)}`;
  const [view, setView] = useState<View | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState("");

  const [loadFailed, setLoadFailed] = useState(false);
  const [contact, setContact] = useState<Contact | null>(null);

  const load = useCallback(async () => {
    setError("");
    setLoadFailed(false);
    try {
      const res = await fetch(url);
      const data = await res.json().catch(() => ({}));
      const c = contactFrom(data);
      if (c) setContact(c);
      if (!res.ok) {
        setError(typeof data.detail === "string" ? data.detail : "This link is not valid");
        return;
      }
      setView(data as View);
    } catch {
      // Network failure (weak signal): let them try again.
      setLoadFailed(true);
      setError("Couldn't load — check your connection");
    }
  }, [url]);

  useEffect(() => {
    void load();
  }, [load]);

  async function send(status: string, label: string) {
    setBusy(true);
    setError("");
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status, note: note.trim() || null }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Could not send");
      setView(data as View);
      setNote("");
      setSaved(`Sent: ${label}. Thank you — the care team can see it now.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not send");
    } finally {
      setBusy(false);
    }
  }

  let body: React.ReactNode;
  if (error && !view) {
    body = (
      <>
        <p className="error">{error}</p>
        {loadFailed ? (
          <button type="button" onClick={() => void load()}>
            Retry
          </button>
        ) : null}
      </>
    );
  } else if (!view) {
    body = <p className="muted">Loading…</p>;
  } else if (view.expired) {
    body = <p>This link has expired. Please call the KushAlaya care team.</p>;
  } else {
    body = (
      <>
        <h1 style={{ fontSize: "1.3rem", margin: "0 0 0.5rem" }}>Emergency hand-off</h1>
        <p style={{ margin: "0 0 0.75rem" }}>For {view.partner_name}</p>
        <dl style={{ margin: "0 0 1rem", display: "grid", gap: "0.35rem" }}>
          <div>
            <dt className="muted">Client</dt>
            <dd style={{ margin: 0, fontWeight: 700 }}>{view.client_name}</dd>
          </div>
          <div>
            <dt className="muted">What happened</dt>
            <dd style={{ margin: 0 }}>{view.what_happened || "Emergency"}{view.opened_at ? ` · ${formatIST(view.opened_at)}` : ""}</dd>
          </div>
          {view.address ? (
            <div>
              <dt className="muted">Address</dt>
              <dd style={{ margin: 0 }}>{view.address}</dd>
            </div>
          ) : null}
          {view.client_phone ? (
            <div>
              <dt className="muted">Phone</dt>
              <dd style={{ margin: 0 }}>
                <a href={`tel:${view.client_phone}`}>{view.client_phone}</a>
              </dd>
            </div>
          ) : null}
        </dl>
        {view.closed ? (
          <p>The care team has closed this emergency. Thank you.</p>
        ) : (
          <>
            <label htmlFor="partner-note">Note (optional)</label>
            <textarea
              id="partner-note"
              rows={2}
              maxLength={500}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. ETA 15 minutes, taking to KIMS"
              style={{ width: "100%", margin: "0.25rem 0 0.75rem" }}
            />
            <div style={{ display: "grid", gap: "0.5rem" }}>
              {view.statuses.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  className={view.last_status === s.value ? "secondary" : undefined}
                  disabled={busy}
                  onClick={() => void send(s.value, s.label)}
                >
                  {s.label}
                  {view.last_status === s.value ? " ✓" : ""}
                </button>
              ))}
            </div>
          </>
        )}
        {saved ? (
          <p role="status" style={{ marginTop: "0.75rem" }}>
            {saved}
          </p>
        ) : null}
        {error ? <p className="error">{error}</p> : null}
      </>
    );
  }

  return (
    <main className={`auth-page ko-login ${portalFont.variable}`}>
      <div className="ko-login-wrap">
        <div className="card auth-card ko-login-card">
          <PublicBrandMark variant="lockup" className="auth-brand-lockup ko-login-logo" />
          {body}
          {contact ? (
            <p style={{ marginTop: "1rem" }}>
              KushAlaya care team: <a href={`tel:${contact.tel}`}>{contact.phone}</a>
            </p>
          ) : null}
        </div>
      </div>
    </main>
  );
}
