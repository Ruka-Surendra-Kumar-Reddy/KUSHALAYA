/** Straight-line distance in metres between two points (haversine). */
export function distanceMeters(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const R = 6_371_000;
  const rad = (d: number) => (d * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}

export const PIN_WARN_METERS = 1000;

/** The home pin is far from where the address geocoded: check-in verification may be wrong. */
export function pinFarFromAddress(
  pin: { lat: number; lng: number } | null | undefined,
  addressPoint: { lat: number; lng: number } | null | undefined,
): number | null {
  if (!pin || !addressPoint) return null;
  const d = distanceMeters(pin, addressPoint);
  return d > PIN_WARN_METERS ? d : null;
}
