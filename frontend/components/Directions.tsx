"use client";

import { MapAppButtons } from "@/components/LiveVisitMap";
import { directionsTarget, mapAppLinks, type LatLng } from "@/lib/live-location";

/**
 * "Directions" to a client's home: one button that opens a choice of
 * Google Maps / Apple Maps / Waze (route from the phone's own location).
 * Uses the saved home pin when there is one, else the address.
 * Shared by the caregiver app and ops (client page, Schedule, roster, alerts).
 * Who sees it and when: docs/MAPS_AND_DIRECTIONS.md. Styles: components/live-visit.css.
 */
export function Directions({
  home,
  address,
  location,
  name,
  label = "Directions",
  className = "",
  summaryClassName = "ks-dir-btn",
}: {
  home?: LatLng | null;
  address?: string | null;
  location?: string | null;
  /** Client name, for the accessible label. */
  name?: string;
  label?: string;
  className?: string;
  summaryClassName?: string;
}) {
  const to = directionsTarget({ home, address, location });
  if (!to) return null;
  return (
    <details className={`ks-directions${className ? ` ${className}` : ""}`}>
      <summary className={summaryClassName} aria-label={name ? `Directions to ${name}'s home` : undefined}>
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M3 11 21 3l-8 18-2-8z" />
        </svg>
        {label}
      </summary>
      <MapAppButtons links={mapAppLinks(to)} lead="Open in" place={name ? `${name}'s home` : "the client's home"} />
    </details>
  );
}
