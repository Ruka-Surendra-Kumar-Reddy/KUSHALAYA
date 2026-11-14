"use client";

import type { FamilyCareStatus } from "@/lib/livewell/familyApi";
import { formatInZone } from "@/lib/ist";
import { useFamilyTimezone } from "@/lib/family-zone";

function pretty(value: string | null | undefined): string {
  if (!value) return "—";
  return value.replace(/_/g, " ");
}

export function FamilyCareStatusCard({ status }: { status: FamilyCareStatus }) {
  const tz = useFamilyTimezone();
  const level = status.level || "unknown";
  const snap = status.snapshot;

  const rows: { label: string; value: string }[] = [];
  if (snap) {
    const add = (label: string, value: string | null | undefined) => {
      if (value) rows.push({ label, value: pretty(value) });
    };
    add("Activity / contact", snap.overall);
    add("Mobility", snap.mobility);
    add("Meals", snap.eating);
    rows.push({
      label: "Medication",
      value:
        snap.medication && snap.medication !== "none"
          ? pretty(snap.medication)
          : "✓ No issue reported",
    });
    add("Falls", snap.falls);
    add("Home safety", snap.home_safety);
  }
  const confirmed = status.confirmed_at
    ? formatInZone(status.confirmed_at, tz)
    : null;

  return (
    <section
      className={`card home-safety-section home-safety-care-status is-${level}`}
      aria-label="Care status"
    >
      <p className="home-safety-care-status-kicker">Care status</p>
      <h2 className="home-safety-care-status-headline">{status.headline}</h2>
      {status.stability_score != null ? (
        <p className="home-safety-care-status-stability">
          KushLife score: <strong>{status.stability_score}</strong>
          {status.stability_delta_from_baseline != null &&
          status.stability_delta_from_baseline !== 0
            ? ` (${status.stability_delta_from_baseline > 0 ? "+" : ""}${status.stability_delta_from_baseline} vs personal normal)`
            : " (personal normal = 50)"}
        </p>
      ) : null}
      {confirmed ? (
        <p className="muted home-safety-care-status-confirmed">
          Last confirmed: {confirmed}
          {snap?.staff_name ? ` · ${snap.staff_name}` : ""}
        </p>
      ) : (
        <p className="muted home-safety-care-status-confirmed">
          No structured check-in yet
        </p>
      )}

      {rows.length > 0 ? (
        <dl className="home-safety-care-status-grid">
          {rows.map((row) => (
            <div key={row.label}>
              <dt>{row.label}</dt>
              <dd>{row.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {snap?.open_request ? (
        <p className="home-safety-care-status-request">
          <strong>Open request:</strong> {snap.open_request}
        </p>
      ) : null}

      {snap?.family_message || snap?.care_manager_note ? (
        <div className="home-safety-care-status-family-msg">
          <h3>Message from Family Partner</h3>
          <p>{snap.family_message || snap.care_manager_note}</p>
        </div>
      ) : null}

      {status.change_summary ? (
        <div className="home-safety-care-status-change">
          <h3>What changed?</h3>
          <p>{status.change_summary}</p>
        </div>
      ) : null}

      {status.reasons && status.reasons.length > 0 && level !== "ok" ? (
        <ul className="home-safety-care-status-reasons">
          {status.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      ) : null}

      <p className="muted home-safety-care-status-disclaimer">
        {status.disclaimer ||
          "Care coordination status from recent check-ins — not a medical diagnosis."}
      </p>
    </section>
  );
}
