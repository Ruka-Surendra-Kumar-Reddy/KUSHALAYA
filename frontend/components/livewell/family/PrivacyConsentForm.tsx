"use client";

import { FormEvent, useState } from "react";
import { withPublicBrand } from "@/lib/public-brand";
import {
  saveConsent,
  type ConsentStatus,
  type PrivacyNotice,
} from "@/lib/livewell/privacyApi";

const ELDER_KEYS = ["care_delivery", "health_data", "location_sharing"];

/** Purposes checklist for the account holder and each client (DPDP #104). Marketing starts off. */
export function PrivacyConsentForm({
  notice,
  status,
  onSaved,
  submitLabel = "I agree",
}: {
  notice: PrivacyNotice;
  status: ConsentStatus;
  onSaved: (next: ConsentStatus) => void;
  submitLabel?: string;
}) {
  const initial: Record<string, boolean> = {};
  for (const p of notice.purposes) {
    const prev = status.consent?.purposes?.[p.key];
    // Optional purposes start unticked until the family chooses (DPDP: consent must be an active choice).
    initial[p.key] = p.required ? true : typeof prev === "boolean" ? prev : false;
  }
  const [purposes, setPurposes] = useState(initial);
  // An active choice: the declaration starts unticked (DPDP) until it has been agreed;
  // after that it shows the saved agreement (ticked), so "Last agreed …" and the box match.
  const [onBehalf, setOnBehalf] = useState(
    status.elders.length > 0 && status.elders.every((el) => !!el.consent && !el.needs_consent),
  );
  const [relationship, setRelationship] = useState(status.elders[0]?.consent?.relationship || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (status.elders.length && !onBehalf) {
      setError("Please confirm you may agree for your family member, or ask them to agree with you.");
      return;
    }
    if (status.elders.length && onBehalf && !relationship.trim()) {
      setError("Please say how you are related to them (for example son, daughter, or self).");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const elderPurposes = Object.fromEntries(ELDER_KEYS.map((k) => [k, !!purposes[k]]));
      const next = await saveConsent({
        purposes,
        elders: status.elders.map((el) => ({
          elder_id: el.elder_id,
          purposes: elderPurposes,
          relationship: relationship.trim() || undefined,
        })),
      });
      onSaved(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="fp-consent-form" onSubmit={(e) => void onSubmit(e)}>
      {notice.purposes.map((p) => (
        <label key={p.key} className="home-safety-check-inline fp-purpose">
          <input
            type="checkbox"
            checked={!!purposes[p.key]}
            disabled={p.required}
            onChange={(e) => setPurposes({ ...purposes, [p.key]: e.target.checked })}
          />
          <span>
            <strong>
              {p.label}
              {p.required ? " (needed for care)" : p.key === "marketing" ? " (optional)" : ""}
            </strong>
            <br />
            <small>{withPublicBrand(p.text)}</small>
          </span>
        </label>
      ))}
      {status.elders.length ? (
        <>
          <label className="home-safety-check-inline fp-purpose">
            <input type="checkbox" checked={onBehalf} onChange={(e) => setOnBehalf(e.target.checked)} />
            <span>
              {status.elders.length === 1
                ? `${status.elders[0].name} agrees to the above, or I am allowed to agree on ${
                    status.elders[0].name.split(" ")[0]
                  }'s behalf.`
                : `${status.elders.map((el) => el.name).join(", ")} agree to the above, or I am allowed to agree on their behalf.`}
            </span>
          </label>
          <label className="home-safety-field">
            Your relationship to them{onBehalf ? " (required)" : ""}
            <input
              value={relationship}
              required={onBehalf}
              aria-required={onBehalf}
              maxLength={60}
              placeholder="e.g. son, daughter, self"
              onChange={(e) => setRelationship(e.target.value)}
            />
          </label>
        </>
      ) : null}
      {error ? <p className="error-text">{error}</p> : null}
      <button type="submit" className="primary" disabled={saving}>
        {saving ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}
