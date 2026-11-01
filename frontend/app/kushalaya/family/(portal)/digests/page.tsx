"use client";

import { withPublicBrand } from "@/lib/public-brand";

import { FormEvent, useEffect, useState } from "react";
import { FamilyShell } from "@/components/livewell/family/FamilyShell";
import { FamilyError } from "@/components/livewell/family/FamilyError";
import { FamilyEmailPrefs } from "@/components/livewell/family/FamilyEmailPrefs";
import { FamilyAlertLevel } from "@/components/livewell/family/FamilyAlertLevel";
import { FamilyLink as Link } from "@/components/livewell/family/FamilyLink";
import { useFamilyTimezone } from "@/lib/family-zone";
import { copyText, whatsappShareUrl } from "@/lib/share";
import { timezoneLabel } from "@/lib/family-contacts";
import {
  fetchFamilyDigestPrefs,
  fetchFamilyDigestPreview,
  updateFamilyDigestPrefs,
  type FamilyDigestPrefs,
} from "@/lib/livewell/familyApi";

export default function FamilyDigestsPage() {
  const [prefs, setPrefs] = useState<FamilyDigestPrefs | null>(null);
  const [preview, setPreview] = useState("");
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const tz = useFamilyTimezone();

  async function load() {
    const [p, d] = await Promise.all([
      fetchFamilyDigestPrefs(),
      fetchFamilyDigestPreview(),
    ]);
    setPrefs(p);
    setPreview(d.text);
  }

  function retry() {
    setLoadError("");
    load().catch((e) => setLoadError(e instanceof Error ? e.message : "Failed to load"));
  }

  useEffect(() => {
    retry();
  }, []);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    if (!prefs) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const next = await updateFamilyDigestPrefs({ ...prefs, digest_timezone: tz || prefs.digest_timezone });
      setPrefs(next);
      const d = await fetchFamilyDigestPreview();
      setPreview(d.text);
      setMessage("Preferences saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function sharePreview() {
    if (!preview) return;
    setError("");
    try {
      if (navigator.share) {
        await navigator.share({ title: withPublicBrand("LiveWell360 care digest"), text: preview });
        return;
      }
    } catch (err) {
      // The person closed the share sheet; anything else (the app's WebView refuses) falls back to copy.
      if (err instanceof Error && err.name === "AbortError") return;
    }
    if (await copyText(preview)) {
      setMessage("Digest copied — paste it into WhatsApp or a message.");
    } else {
      setError("Couldn't copy here. Use “Send on WhatsApp” instead.");
    }
  }

  return (
    <FamilyShell title="Notifications" subtitle="Choose what you hear about, and who else hears it">
      {/* The one place for notification settings (My details links here). */}
      <FamilyAlertLevel />
      <FamilyEmailPrefs />
      <FamilyError message={loadError} onRetry={retry} what="your notification settings" />
      {error ? <p className="error-text">{error}</p> : null}
      {message ? <p className="home-safety-family-success">{message}</p> : null}

      {!prefs ? (
        <p>Loading…</p>
      ) : (
        <form className="card home-safety-section" onSubmit={(e) => void onSave(e)}>
          <h2>Care digest</h2>
          <label className="home-safety-check-inline">
            <input
              type="checkbox"
              checked={prefs.digest_enabled}
              onChange={(e) => setPrefs({ ...prefs, digest_enabled: e.target.checked })}
            />
            <span>Send care digests</span>
          </label>
          <label className="home-safety-field">
            Channel
            <select
              value={prefs.digest_channel}
              onChange={(e) => setPrefs({ ...prefs, digest_channel: e.target.value })}
            >
              <option value="whatsapp">WhatsApp-ready text</option>
              <option value="email">Email</option>
              <option value="none">Off</option>
            </select>
          </label>
          <label className="home-safety-field">
            How often
            <select
              value={prefs.digest_cadence}
              onChange={(e) => setPrefs({ ...prefs, digest_cadence: e.target.value })}
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
            </select>
          </label>
          {/* One timezone setting: "Where you live" on My details. */}
          <p className="muted">
            Digests arrive in your time: <strong>{timezoneLabel(tz || prefs.digest_timezone)}</strong>.{" "}
            <Link href="/kushalaya/family/details" className="fh-inline-tap">
              Change where you live
            </Link>
          </p>
          <button type="submit" className="primary" disabled={saving}>
            {saving ? "Saving…" : "Save preferences"}
          </button>
        </form>
      )}

      <section className="card home-safety-section">
        <h2>Preview</h2>
        <p className="muted home-safety-section-hint">
          This is what your next digest will say. You can also copy it and share it with family.
        </p>
        <pre className="home-safety-family-digest-preview">{preview}</pre>
        <button type="button" className="secondary" onClick={() => void sharePreview()}>
          Share / copy digest
        </button>{" "}
        <a className="button secondary" href={whatsappShareUrl(preview)} target="_blank" rel="noopener noreferrer">
          Send on WhatsApp
        </a>
      </section>
    </FamilyShell>
  );
}
