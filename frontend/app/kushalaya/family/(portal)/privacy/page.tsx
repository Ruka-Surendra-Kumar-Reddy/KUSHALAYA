"use client";

import { FormEvent, useEffect, useState } from "react";
import "@/components/livewell/family/privacy.css";
import { withPublicBrand } from "@/lib/public-brand";
import { familyDate } from "@/lib/livewell/familyTime";
import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import { FamilyError } from "@/components/livewell/family/FamilyError";
import { PrivacyConsentForm } from "@/components/livewell/family/PrivacyConsentForm";
import {
  downloadMyData,
  fetchConsentStatus,
  fetchPrivacyNotice,
  requestAccountDelete,
  type ConsentStatus,
  type PrivacyNotice,
} from "@/lib/livewell/privacyApi";

function when(iso?: string | null) {
  return familyDate(iso);
}

/** DPDP (#104): notice, consent choices, download my data, delete my account. */
export default function FamilyPrivacyPage() {
  const [notice, setNotice] = useState<PrivacyNotice | null>(null);
  const [status, setStatus] = useState<ConsentStatus | null>(null);
  const [loadError, setLoadError] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [scope, setScope] = useState<"account" | "household">("account");
  const [reason, setReason] = useState("");
  const [confirm, setConfirm] = useState(false);

  function load() {
    setLoadError("");
    Promise.all([fetchPrivacyNotice(), fetchConsentStatus()])
      .then(([n, s]) => {
        setNotice(n);
        setStatus(s);
      })
      .catch((e) => setLoadError(e instanceof Error ? e.message : "Failed to load"));
  }

  useEffect(load, []);

  async function onDownload() {
    setBusy(true);
    setError("");
    try {
      await downloadMyData();
      setMessage("Your data is downloading — a file with everything.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(e: FormEvent) {
    e.preventDefault();
    if (!confirm) return;
    setBusy(true);
    setError("");
    try {
      await requestAccountDelete(scope, reason);
      setMessage("Request sent. Our team will review it and confirm within 30 days.");
      setStatus(await fetchConsentStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send the request");
    } finally {
      setBusy(false);
    }
  }

  const officer = notice?.grievance_officer;
  const pending = status?.pending_delete_request;

  return (
    <FamilyShell title="Privacy & your data" subtitle="What we keep, what you agreed to, and your rights">
      <FamilyError message={loadError} onRetry={load} what="your privacy settings" />
      {message ? <p className="home-safety-family-success">{message}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}
      {!notice || !status ? (
        loadError ? null : <p>Loading…</p>
      ) : (
        <>
          <section className="card home-safety-section">
            <h2>Your choices</h2>
            {status.consent ? (
              <p>
                Last agreed {when(status.consent.created_at)} (notice version {status.consent.notice_version}).
              </p>
            ) : null}
            <PrivacyConsentForm
              notice={notice}
              status={status}
              submitLabel="Save my choices"
              onSaved={(s) => {
                setStatus(s);
                setMessage("Your choices are saved.");
              }}
            />
          </section>

          <section className="card home-safety-section">
            <h2>Download my data</h2>
            <p>
              A file with everything we hold about you and your household: details, consents, visits, orders and
              payments, alerts, contacts and a list of documents.
            </p>
            <button type="button" className="primary" disabled={busy} onClick={() => void onDownload()}>
              Download my data
            </button>
          </section>

          <section className="card home-safety-section">
            <h2>Delete my account</h2>
            {pending ? (
              <p>
                You asked on {when(pending.created_at)} to delete{" "}
                {pending.scope === "household" ? "your account and your family member's records" : "your account"}.
                It is waiting for review.
              </p>
            ) : (
              <form className="fp-consent-form" onSubmit={(e) => void onDelete(e)}>
                <p>
                  We will erase or anonymise your personal data within 30 days. Invoices and payment records are
                  kept for 8 years because the law requires it, with names and contact details removed.
                </p>
                <label className="home-safety-check-inline">
                  <input type="radio" name="scope" checked={scope === "account"} onChange={() => setScope("account")} />
                  <span>Only my login and my details</span>
                </label>
                <label className="home-safety-check-inline">
                  <input
                    type="radio"
                    name="scope"
                    checked={scope === "household"}
                    onChange={() => setScope("household")}
                  />
                  <span>My login and my family member&rsquo;s care records (main family member only)</span>
                </label>
                <label className="home-safety-field">
                  Reason (optional)
                  <textarea value={reason} maxLength={2000} rows={2} onChange={(e) => setReason(e.target.value)} />
                </label>
                <label className="home-safety-check-inline">
                  <input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} />
                  <span>I understand this cannot be undone once approved.</span>
                </label>
                <div className="fp-actions">
                  <button type="submit" className="fp-danger" disabled={busy || !confirm}>
                    Ask to delete
                  </button>
                </div>
              </form>
            )}
          </section>

          <section className="card home-safety-section fp-notice">
            <h2>Privacy notice</h2>
            <p>
              <small>Version {notice.version}</small>
            </p>
            {notice.sections.map((s) => (
              <div key={s.heading}>
                <h3>{s.heading}</h3>
                <p>{withPublicBrand(s.body)}</p>
              </div>
            ))}
            {officer ? (
              <>
                <h3>Grievance Officer</h3>
                <p>
                  {officer.name}
                  {officer.role ? ` — ${officer.role}` : ""}
                  <br />
                  <a href={`mailto:${officer.email}`}>{officer.email}</a> ·{" "}
                  <a href={`tel:${officer.phone.replace(/\s/g, "")}`}>{officer.phone}</a>
                  <br />
                  We reply within {officer.response_days ?? 30} days.
                </p>
              </>
            ) : null}
          </section>
        </>
      )}
    </FamilyShell>
  );
}
