"use client";

import { useEffect, useRef, useState } from "react";
import type { LatLng, MapLink } from "@/lib/live-location";
import "./live-visit.css";

/* Leaflet + OpenStreetMap tiles, loaded from cdnjs only when a map is shown (no API key). */
const LEAFLET_JS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js";
const LEAFLET_CSS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css";
// Subresource integrity (sha512 from cdnjs, checked against the files).
const LEAFLET_JS_SRI = "sha512-puJW3E/qXDqYp9IfhAI54BJEaWIfloJ7JWs7OeD5i6ruC9JZL1gERT1wjtwXFlh7CjE7ZJ+/vcRZRkIYIb6p4g==";
const LEAFLET_CSS_SRI = "sha512-h9FcoyWjHcOcmEVkxOfTLnmZFWIH0iZhZT1H2TbOq55xssQGEJHEaIm+PgoUaZbRvQTNTluNOEfb1ZRy6D3BOw==";
const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
// Road route from the person on the way to the home (OSRM, no API key). If it doesn't
// answer, a dashed straight line stays instead.
const ROUTE_API = "https://router.project-osrm.org/route/v1/driving";
// OSRM times are for empty roads; Indian city traffic is slower.
const CITY_TRAFFIC = 1.5;
const OSM_ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors';

type LeafletMap = { remove(): void; fitBounds(b: unknown, o?: unknown): void; setView(c: unknown, z: number): void };
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type LeafletNS = any;

let leafletPromise: Promise<LeafletNS> | null = null;

function loadLeaflet(): Promise<LeafletNS> {
  const w = window as unknown as { L?: LeafletNS };
  if (w.L) return Promise.resolve(w.L);
  if (leafletPromise) return leafletPromise;
  leafletPromise = new Promise((resolve, reject) => {
    if (!document.querySelector(`link[href="${LEAFLET_CSS}"]`)) {
      const css = document.createElement("link");
      css.rel = "stylesheet";
      css.href = LEAFLET_CSS;
      css.integrity = LEAFLET_CSS_SRI;
      css.crossOrigin = "anonymous";
      document.head.appendChild(css);
    }
    const s = document.createElement("script");
    s.src = LEAFLET_JS;
    s.integrity = LEAFLET_JS_SRI;
    s.crossOrigin = "anonymous";
    s.async = true;
    s.onload = () => (w.L ? resolve(w.L) : reject(new Error("no leaflet")));
    s.onerror = () => {
      leafletPromise = null;
      reject(new Error("map failed to load"));
    };
    document.head.appendChild(s);
  });
  return leafletPromise;
}

/** Small map with the caregiver (filled dot) and the client's home (ring). */
export function LiveVisitMap({
  caregiver,
  home,
  caregiverLabel,
  onRoute,
}: {
  caregiver: LatLng;
  home: LatLng | null;
  caregiverLabel: string;
  /** Road time (city traffic allowed) and distance, when the route is known. */
  onRoute?: (r: { minutes: number; km: number } | null) => void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<LeafletMap | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const cgMarker = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const homeMarker = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const routeLine = useRef<any>(null);
  const Lref = useRef<LeafletNS>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [route, setRoute] = useState<{ minutes: number; km: number } | null>(null);
  const onRouteRef = useRef(onRoute);
  onRouteRef.current = onRoute;
  useEffect(() => onRouteRef.current?.(route), [route]);

  // Build the map once; position changes only move the markers (below).
  useEffect(() => {
    let cancelled = false;
    loadLeaflet()
      .then((L) => {
        if (cancelled || !box.current) return;
        const m = L.map(box.current, { zoomControl: false, attributionControl: true, scrollWheelZoom: false });
        L.tileLayer(TILES, { maxZoom: 19, attribution: OSM_ATTRIBUTION }).addTo(m);
        Lref.current = L;
        map.current = m;
        setReady(true);
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
      map.current?.remove();
      map.current = null;
      cgMarker.current = null;
      homeMarker.current = null;
      routeLine.current = null;
    };
  }, []);

  // Each poll returns new objects, so depend on the numbers only.
  useEffect(() => {
    const L = Lref.current;
    const m = map.current;
    if (!ready || !L || !m) return;
    const cg = [caregiver.lat, caregiver.lng];
    if (cgMarker.current) {
      cgMarker.current.setLatLng(cg);
      cgMarker.current.setTooltipContent(caregiverLabel);
    } else {
      cgMarker.current = L.circleMarker(cg, { radius: 9, color: "#fff", weight: 3, fillColor: "#1f7a5c", fillOpacity: 1 })
        .addTo(m)
        .bindTooltip(caregiverLabel);
    }
    if (home) {
      const h = [home.lat, home.lng];
      if (homeMarker.current) homeMarker.current.setLatLng(h);
      else
        homeMarker.current = L.circleMarker(h, { radius: 9, color: "#b4532a", weight: 3, fillColor: "#fff", fillOpacity: 1 })
          .addTo(m)
          .bindTooltip("Home");
      m.fitBounds([cg, h], { padding: [28, 28], maxZoom: 16 });
      // Straight dashed line at once; swapped for the road route when it arrives.
      if (routeLine.current) routeLine.current.setLatLngs([cg, h]).setStyle({ dashArray: "6 8", opacity: 0.6 });
      else
        routeLine.current = L.polyline([cg, h], { color: "#1f7a5c", weight: 5, opacity: 0.6, dashArray: "6 8" }).addTo(m);
      const ac = new AbortController();
      fetch(`${ROUTE_API}/${caregiver.lng},${caregiver.lat};${home.lng},${home.lat}?overview=full&geometries=geojson`, { signal: ac.signal })
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => {
          const coords: [number, number][] | undefined = d?.routes?.[0]?.geometry?.coordinates;
          if (!coords?.length || !routeLine.current || !map.current) return;
          routeLine.current.setLatLngs(coords.map(([x, y]) => [y, x])).setStyle({ dashArray: null, opacity: 0.85 });
          const r = d.routes[0] as { duration: number; distance: number };
          setRoute({ minutes: Math.max(1, Math.round((r.duration * CITY_TRAFFIC) / 60)), km: Math.round(r.distance / 100) / 10 });
          map.current.fitBounds(routeLine.current.getBounds(), { padding: [28, 28], maxZoom: 16 });
        })
        .catch(() => undefined);
      return () => ac.abort();
    } else {
      homeMarker.current?.remove();
      homeMarker.current = null;
      routeLine.current?.remove();
      routeLine.current = null;
      setRoute(null);
      m.setView(cg, 15);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, caregiver.lat, caregiver.lng, home?.lat, home?.lng, caregiverLabel]);

  if (failed) {
    return <p className="lv-map-fallback">The map couldn&apos;t load. Use a map app below to see where they are.</p>;
  }
  return (
    <div className="lv-map-wrap">
      <div ref={box} className="lv-map" role="img" aria-label={home ? `Map showing ${caregiverLabel} and the route to the home` : `Map showing ${caregiverLabel}`} />
      {route && home ? (
        <p className="lv-route-chip" aria-live="polite">
          <strong>{route.minutes < 60 ? `${route.minutes} min` : `${Math.floor(route.minutes / 60)} h ${route.minutes % 60} min`}</strong>
          <span>{route.km} km by road</span>
        </p>
      ) : null}
    </div>
  );
}

/** "Open in Google Maps / Apple Maps / Waze" buttons. */
export function MapAppButtons({ links, lead, place }: { links: MapLink[]; lead?: string; place?: string }) {
  if (!links.length) return null;
  return (
    <div className="lv-apps">
      {lead ? <span className="lv-apps-lead">{lead}</span> : null}
      {links.map((l) => (
        <a
          key={l.label}
          className="lv-app"
          href={l.href}
          target="_blank"
          rel="noreferrer"
          aria-label={`${place ? `Directions to ${place} in` : "Open in"} ${l.label} (opens in a new tab)`}
        >
          {l.label}
        </a>
      ))}
    </div>
  );
}
