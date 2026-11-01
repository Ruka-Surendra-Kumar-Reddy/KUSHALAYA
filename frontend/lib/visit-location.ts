/**
 * Where a visit was logged from (backend app/livewell/visit_location.py).
 * The caregiver app must send it for check-in and finishing; ops staff send it when the browser gives one.
 */
import { getBestPosition } from "./caregiverPortal";

export type LocationPayload = { latitude: number; longitude: number; accuracy: number | null };

export type VisitPoint = {
  lat: number;
  lng: number;
  accuracy_m: number | null;
  distance_m: number | null;
  away: boolean | null;
};

/** Staff only (ops job list): the check-in / check-out points. */
export type VisitLocation = { has_home_pin: boolean; checkin: VisitPoint | null; checkout: VisitPoint | null };

export function toLocationPayload(pos: { coords: { latitude: number; longitude: number; accuracy?: number | null } }): LocationPayload {
  const acc = pos.coords.accuracy;
  return {
    latitude: pos.coords.latitude,
    longitude: pos.coords.longitude,
    accuracy: typeof acc === "number" && Number.isFinite(acc) ? Math.round(acc) : null,
  };
}

/** Caregiver app: the location or an error (the caller shows LOCATION_STEPS and Try again). */
export async function requireLocation(maxWaitMs = 12000): Promise<LocationPayload> {
  // Hard stop: a location prompt left unanswered (iPad / iPhone) never times out on
  // its own, which left "Finding you…" spinning with no way forward.
  return toLocationPayload(await withTimeout(getBestPosition(maxWaitMs), maxWaitMs + 10_000));
}

/** Rejects when `p` has not settled within `ms`. */
export function withTimeout<T>(p: Promise<T>, ms: number, message = "Could not get your location in time"): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(message)), ms);
    p.then(
      (v) => {
        clearTimeout(timer);
        resolve(v);
      },
      (e) => {
        clearTimeout(timer);
        reject(e);
      },
    );
  });
}

/** Ops staff: the location if the browser gives one quickly, else null (never blocks). */
export async function optionalLocation(maxWaitMs = 8000): Promise<LocationPayload | null> {
  try {
    if (typeof navigator === "undefined" || !navigator.geolocation) return null;
    return await requireLocation(maxWaitMs);
  } catch {
    return null;
  }
}

export function locationTitle(action: "checked_in" | "completed"): string {
  return action === "checked_in" ? "Turn on location to check in" : "Turn on location to finish the visit";
}

export const LOCATION_STEPS = [
  "Turn on Location in your phone or iPad settings (Privacy → Location Services).",
  "Allow location for this app when your browser asks (or in its site settings).",
  "Step outside or near a window if it is slow, then tap Try again.",
];

export function distanceText(m: number): string {
  return m < 1000 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(1)} km`;
}

export function mapsUrl(lat: number, lng: number): string {
  return `https://www.google.com/maps/search/?api=1&query=${lat.toFixed(6)},${lng.toFixed(6)}`;
}

/** "Check-in 2.3 km from home" / "Check-in location (no home pin)" / "Check-in: no location". */
export function pointText(label: string, p: VisitPoint | null | undefined, hasPin: boolean): string {
  if (!p) return `${label}: no location`;
  if (!hasPin || p.distance_m == null) return `${label} location (no home pin)`;
  return `${label} ${distanceText(p.distance_m)} from home${p.away ? " — away from home" : ""}`;
}

export type PlaceLine = { text: string; href: string | null; away: boolean };

/** Check-in / check-out lines for the ops visit history (staff only). */
export function placeLines(
  loc: VisitLocation | null | undefined,
  status: string,
): PlaceLine[] {
  if (!loc || (status !== "checked_in" && status !== "completed")) return [];
  const rows: [string, VisitPoint | null][] = [["Check-in", loc.checkin]];
  if (status === "completed") rows.push(["Check-out", loc.checkout]);
  return rows.map(([label, p]) => ({
    text: pointText(label, p, loc.has_home_pin),
    href: p ? mapsUrl(p.lat, p.lng) : null,
    away: Boolean(p?.away),
  }));
}
