"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import type { Map as LeafletMap, LayerGroup } from "leaflet";

export type MapPin = {
  id: string;
  lat: number;
  lng: number;
  /** Plain text lines shown in the popup; the first one is the title. */
  lines: string[];
  /** green = at home, amber = away from home, blue = no home to compare with. */
  tone?: "ok" | "warn" | "neutral";
};

export type MapHome = { lat: number; lng: number; radius_m: number };

const TONE = { ok: "#16a34a", warn: "#d97706", neutral: "#1b4f9c" } as const;
const HYDERABAD: [number, number] = [17.385, 78.4867];

function esc(text: string): string {
  return text.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c] as string);
}

/**
 * OpenStreetMap view of where visits were logged, next to the client's home and
 * its allowed radius. Leaflet touches `window`, so it is imported inside the
 * effect; circle markers are used throughout so no marker images are needed.
 */
export function VisitMap({
  pins,
  home,
  focusId,
  height = 320,
  onPick,
}: {
  pins: MapPin[];
  home?: MapHome | null;
  /** Pin to fly to and open. */
  focusId?: string | null;
  height?: number;
  /** When set, a click on the map reports that point (used to place the home pin). */
  onPick?: (lat: number, lng: number) => void;
}) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<LeafletMap | null>(null);
  const layer = useRef<LayerGroup | null>(null);
  const markers = useRef<Record<string, { openPopup: () => void }>>({});
  const pick = useRef(onPick);
  pick.current = onPick;
  // Callers pass fresh arrays on every render; redraw only when the data changes,
  // otherwise typing in a form next to the map would reset its zoom each keystroke.
  const dataKey = JSON.stringify([pins, home ?? null]);

  useEffect(() => {
    let cancelled = false;
    void import("leaflet").then((L) => {
      if (cancelled || !el.current) return;
      if (!map.current) {
        map.current = L.map(el.current, { scrollWheelZoom: false }).setView(HYDERABAD, 11);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19,
          attribution: "&copy; OpenStreetMap contributors",
        }).addTo(map.current);
        map.current.on("click", (e) => pick.current?.(e.latlng.lat, e.latlng.lng));
        layer.current = L.layerGroup().addTo(map.current);
      }
      const group = layer.current!;
      group.clearLayers();
      markers.current = {};
      const bounds: [number, number][] = [];

      if (home) {
        L.circle([home.lat, home.lng], {
          radius: home.radius_m,
          color: "#16a34a",
          weight: 1,
          fillOpacity: 0.12,
        }).addTo(group);
        L.circleMarker([home.lat, home.lng], {
          radius: 7,
          color: "#fff",
          weight: 2,
          fillColor: "#0f172a",
          fillOpacity: 1,
        })
          .bindPopup(`<strong>Client's home</strong><br>Allowed radius ${home.radius_m} m`)
          .addTo(group);
        bounds.push([home.lat, home.lng]);
      }

      for (const pin of pins) {
        const [title, ...rest] = pin.lines;
        const marker = L.circleMarker([pin.lat, pin.lng], {
          radius: 9,
          color: "#fff",
          weight: 2,
          fillColor: TONE[pin.tone || "neutral"],
          fillOpacity: 0.95,
        })
          .bindPopup(`<strong>${esc(title || "Visit")}</strong>${rest.map((l) => `<br>${esc(l)}`).join("")}`)
          .addTo(group);
        markers.current[pin.id] = marker;
        bounds.push([pin.lat, pin.lng]);
      }

      if (bounds.length === 1) map.current.setView(bounds[0], 16);
      else if (bounds.length > 1) map.current.fitBounds(bounds, { padding: [32, 32], maxZoom: 17 });
      // The container may have been hidden (tab switch) when Leaflet measured it.
      setTimeout(() => map.current?.invalidateSize(), 0);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- dataKey stands for pins + home
  }, [dataKey]);

  useEffect(() => {
    if (!focusId) return;
    const pin = pins.find((p) => p.id === focusId);
    const marker = markers.current[focusId];
    if (pin && marker && map.current) {
      map.current.setView([pin.lat, pin.lng], 17);
      marker.openPopup();
      el.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusId, dataKey]);

  useEffect(
    () => () => {
      map.current?.remove();
      map.current = null;
    },
    [],
  );

  return <div ref={el} className="visit-map" style={{ height }} role="application" aria-label="Visit map" />;
}
