"use client";

import { LOCATION_STEPS, locationTitle } from "@/lib/visit-location";

/** Shown when check-in / finishing could not get a location: short steps and Try again. */
export function LocationNeeded({
  action,
  busy,
  onRetry,
  onCancel,
}: {
  action: "checked_in" | "completed";
  busy: boolean;
  onRetry: () => void;
  onCancel?: () => void;
}) {
  return (
    <div className="cg-note is-warn" role="alert">
      <strong>{locationTitle(action)}</strong>
      <ol className="cg-loc-steps">
        {LOCATION_STEPS.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ol>
      <div className="cg-confirm-btns">
        {onCancel ? (
          <button type="button" className="cg-btn is-ghost" onClick={onCancel}>
            Not now
          </button>
        ) : null}
        <button type="button" className="cg-btn" disabled={busy} onClick={onRetry}>
          {busy ? "Finding you…" : "Try again"}
        </button>
      </div>
    </div>
  );
}
