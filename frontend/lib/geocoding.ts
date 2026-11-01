import { api } from "./api";

export type GeocodeResult = {
  latitude: number;
  longitude: number;
};

export async function previewGeocode(
  address: string,
): Promise<GeocodeResult | null> {
  const query = address.trim();
  if (query.length < 3) return null;
  try {
    return await api<GeocodeResult>(
      `/api/v1/geocode?address=${encodeURIComponent(query)}`,
    );
  } catch {
    return null;
  }
}

export function formatCoordinates(
  latitude: number | string | null | undefined,
  longitude: number | string | null | undefined,
): string {
  const lat = typeof latitude === "string" ? parseFloat(latitude) : latitude;
  const lon = typeof longitude === "string" ? parseFloat(longitude) : longitude;
  if (lat == null || lon == null || Number.isNaN(lat) || Number.isNaN(lon)) {
    return "";
  }
  return `${lat.toFixed(6)}, ${lon.toFixed(6)}`;
}
