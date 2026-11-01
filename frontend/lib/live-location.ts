import { api } from "./api";

/** Live "on the way" block — backend app/livewell/live_location.py. */
export type LatLng = { lat: number; lng: number };

export type LiveOnTheWay = {
  state: "on_the_way";
  job_id?: number;
  title?: string;
  caregiver_first_name: string;
  home: LatLng | null;
  destination: string;
  position: (LatLng & { accuracy_m: number | null }) | null;
  updated_at: string | null;
  stale: boolean;
  distance_km: number | null;
  eta_minutes: number | null;
  eta_label: string;
  /** "/track/<token>": the no-login tracking page for this trip (family host). */
  track_path?: string | null;
};

/** Full tracking link on the family site, from any page (ops, family, localhost). */
export function trackUrl(path: string | null | undefined): string {
  if (!path || typeof window === "undefined") return "";
  const { protocol, hostname, host } = window.location;
  if (hostname.startsWith("ops.")) return `${protocol}//family.${hostname.slice(4)}${path}`;
  if (hostname.startsWith("family.") || hostname.startsWith("staging-family.")) return `${protocol}//${host}${path}`;
  if (hostname.startsWith("www.")) return `${protocol}//family.${hostname.slice(4)}${path}`;
  return `${protocol}//${host}/kushalaya/family${path}`; // localhost / IP: no family host
}

/** What the public tracking page gets (no login). Never the client's address text. */
export type PublicTrack =
  | {
      state: "on_the_way";
      name: string;
      title: string;
      position: (LatLng & { accuracy_m: number | null }) | null;
      /** The client's home point, for the route on the map (no address text). */
      home: LatLng | null;
      updated_at: string | null;
      stale: boolean;
      eta_minutes: number | null;
      eta_label: string;
    }
  | { state: "arrived"; name: string; title: string; arrived_label: string }
  | { state: "ended"; name: string; title: string };

export type LiveArrived = {
  state: "arrived";
  job_id: number;
  title: string;
  caregiver_first_name: string;
  arrived_at: string;
  arrived_label: string;
};

export type LiveVisit = LiveOnTheWay | LiveArrived;

export function fetchFamilyLiveVisit() {
  return api<{ live: LiveVisit | null }>("/api/v1/home-safety/family/live-visit");
}

export function sendMyJobLocation(jobId: number, pos: GeolocationPosition) {
  return api<{ tracking: boolean; status: string }>(`/api/v1/caregiver-portal/jobs/${jobId}/location`, {
    method: "POST",
    body: JSON.stringify({
      latitude: pos.coords.latitude,
      longitude: pos.coords.longitude,
      accuracy: Number.isFinite(pos.coords.accuracy) ? pos.coords.accuracy : null,
    }),
  });
}

const ll = (p: LatLng) => `${p.lat},${p.lng}`;

export type MapLink = { label: string; href: string };

/**
 * "Open in" links for Google Maps, Apple Maps and Waze.
 * `from` is optional (the phone's own location is used when absent);
 * `to` is coordinates or a free-text address.
 */
export function mapAppLinks(to: LatLng | string, from?: LatLng | null): MapLink[] {
  const dest = typeof to === "string" ? to : ll(to);
  const g = new URLSearchParams({ api: "1", destination: dest });
  if (from) g.set("origin", ll(from));
  const a = new URLSearchParams({ daddr: dest });
  if (from) a.set("saddr", ll(from));
  const w = typeof to === "string" ? `q=${encodeURIComponent(to)}` : `ll=${encodeURIComponent(dest)}`;
  return [
    { label: "Google Maps", href: `https://www.google.com/maps/dir/?${g.toString()}` },
    { label: "Apple Maps", href: `https://maps.apple.com/?${a.toString()}` },
    { label: "Waze", href: `https://waze.com/ul?${w}&navigate=yes` },
  ];
}

/**
 * Where "Directions" should lead: the job's own location when it differs from the
 * home address (e.g. a hospital visit), else the client's saved home pin, else the address.
 */
export function directionsTarget(o: {
  home?: LatLng | null;
  address?: string | null;
  location?: string | null;
}): LatLng | string | null {
  const addr = (o.address || "").trim();
  const loc = (o.location || "").trim();
  if (loc && loc !== addr) return loc;
  if (o.home && Number.isFinite(o.home.lat) && Number.isFinite(o.home.lng)) return { lat: o.home.lat, lng: o.home.lng };
  return addr || loc || null;
}

/** Links that show where the caregiver is now (family / staff view). */
export function caregiverLocationLinks(live: LiveOnTheWay): MapLink[] {
  if (!live.position) return [];
  const here = { lat: live.position.lat, lng: live.position.lng };
  const home = live.home ?? (live.destination || null);
  const [google, apple] = home ? mapAppLinks(home, here) : mapAppLinks(here);
  return [google, apple, { label: "Waze", href: `https://waze.com/ul?ll=${encodeURIComponent(ll(here))}&navigate=yes` }];
}

/** "Ravi is on the way — about 12 min away" */
export function liveHeadline(live: LiveOnTheWay): string {
  const who = live.caregiver_first_name || "Your caregiver";
  if (!live.position) return `${who} is on the way`;
  if (live.eta_label === "almost there") return `${who} is on the way — almost there`;
  return live.eta_label ? `${who} is on the way — ${live.eta_label} away` : `${who} is on the way`;
}

/** Short ops label: "on the way · 12 min". */
export function liveShort(live: LiveOnTheWay | null | undefined): string {
  if (!live) return "on the way";
  if (!live.position) return "on the way · no location yet";
  const eta = live.eta_minutes === 0 ? "arriving" : live.eta_minutes != null ? `${live.eta_minutes} min` : "";
  return `on the way${eta ? ` · ${eta}` : ""}${live.stale ? " · last seen a while ago" : ""}`;
}

export const SHARE_EVERY_MS = 30_000;
export const SHARE_MAX_BACKOFF_MS = 5 * 60_000;

/**
 * Should sharing keep trying after this error? The api() client throws plain Errors
 * (no status), so this reads the message: network failures (TypeError), auth
 * expiry (401 — api() refreshes the session) and 5xx / gateway errors are
 * transient. Anything else is the server's own 400/403/404 answer: stop.
 */
export function isTransientShareError(e: unknown): boolean {
  if (e instanceof TypeError) return true;
  const m = (e instanceof Error ? e.message : String(e ?? "")).toLowerCase();
  return /internal server error|bad gateway|service unavailable|gateway time-?out|too many requests|not authenticated|invalid token|could not validate credentials|user not found|failed to fetch|network|timed? ?out|^$/.test(
    m,
  );
}

/**
 * Share the phone's position for one job while the app is open.
 * Sends at most once every 30 s; stops when the server says the job is no
 * longer on the way, or when the returned stop() is called.
 */
export function startLiveSharing(
  jobId: number,
  handlers: { onDenied?: () => void; onStopped?: () => void } = {},
): () => void {
  if (typeof navigator === "undefined" || !navigator.geolocation) {
    handlers.onDenied?.();
    return () => undefined;
  }
  let last = 0;
  let stopped = false;
  let pending: GeolocationPosition | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let failures = 0;

  const stop = () => {
    if (stopped) return;
    stopped = true;
    navigator.geolocation.clearWatch(watchId);
    if (timer) clearTimeout(timer);
  };

  const flush = () => {
    timer = null;
    if (stopped || !pending) return;
    const pos = pending;
    pending = null;
    last = Date.now();
    sendMyJobLocation(jobId, pos)
      .then((r) => {
        if (!r.tracking) {
          stop();
          handlers.onStopped?.();
        }
      })
      .then(() => {
        failures = 0;
      })
      .catch((e) => {
        if (isTransientShareError(e)) {
          // Offline, signed-out-for-a-moment (401) or server trouble (5xx): back off and retry.
          failures += 1;
          const backoff = Math.min(SHARE_EVERY_MS * 2 ** (failures - 1), SHARE_MAX_BACKOFF_MS);
          last = Date.now() + backoff - SHARE_EVERY_MS;
          if (stopped) return;
          if (!pending) pending = pos; // resend the last fix even if the phone hasn't moved
          if (!timer) timer = setTimeout(flush, backoff);
          return;
        }
        // 400/403/404 — job no longer on the way: stop quietly; the visit still works.
        stop();
        handlers.onStopped?.();
      });
  };

  const watchId = navigator.geolocation.watchPosition(
    (pos) => {
      pending = pos;
      const wait = last + SHARE_EVERY_MS - Date.now();
      if (wait <= 0) flush();
      else if (!timer) timer = setTimeout(flush, wait);
    },
    (err) => {
      if (err.code === err.PERMISSION_DENIED) {
        stop();
        handlers.onDenied?.();
      }
    },
    { enableHighAccuracy: true, maximumAge: 15_000, timeout: 60_000 },
  );
  return stop;
}
