/**
 * Ads tracking for the public website only: Meta Pixel and Google tag, loaded only after
 * the visitor presses Accept. Page addresses and event names go out; never names, phone
 * numbers or anything typed into a form. IDs are baked in at build (.env.local).
 */

const CONSENT_KEY = "ks_cookie_consent";
export const COOKIE_SETTINGS_EVENT = "ks-cookie-settings";

export type Consent = "accepted" | "declined";
export type TrackEvent = "lead" | "contact" | "view_plans";

type Fn = (...args: unknown[]) => void;
type TrackingWindow = Window & { fbq?: Fn & { queue?: unknown[][] }; gtag?: Fn; dataLayer?: unknown[] };

const META_EVENT: Record<TrackEvent, string> = { lead: "Lead", contact: "Contact", view_plans: "ViewContent" };
const GOOGLE_EVENT: Record<TrackEvent, string> = { lead: "generate_lead", contact: "contact", view_plans: "view_item_list" };

export function metaPixelId(): string {
  return (process.env.NEXT_PUBLIC_META_PIXEL_ID || "").trim();
}

/** One or more Google IDs, comma separated (G-… for Analytics, AW-… for Ads). */
export function googleTagIds(): string[] {
  return (process.env.NEXT_PUBLIC_GOOGLE_TAG_ID || "")
    .split(",")
    .map((id) => id.trim())
    .filter(Boolean);
}

export function trackingConfigured(): boolean {
  return Boolean(metaPixelId() || googleTagIds().length);
}

export function getConsent(): Consent | null {
  try {
    const v = localStorage.getItem(CONSENT_KEY);
    return v === "accepted" || v === "declined" ? v : null;
  } catch {
    return null;
  }
}

export function setConsent(value: Consent): void {
  try {
    localStorage.setItem(CONSENT_KEY, value);
  } catch {
    // Private windows can refuse storage: the notice simply asks again next visit.
  }
}

function addScript(src: string): void {
  const s = document.createElement("script");
  s.async = true;
  s.src = src;
  document.head.appendChild(s);
}

let loaded = false;

/** Safe to call repeatedly. Does nothing without Accept or without IDs. */
export function loadTrackers(): void {
  if (loaded || typeof window === "undefined" || getConsent() !== "accepted" || !trackingConfigured()) return;
  loaded = true;
  const w = window as TrackingWindow;
  const pixel = metaPixelId();
  if (pixel) {
    const fbq = ((...args: unknown[]) => {
      fbq.queue?.push(args);
    }) as Fn & { queue?: unknown[][]; callMethod?: Fn; loaded?: boolean; version?: string; push?: Fn };
    fbq.queue = [];
    fbq.loaded = true;
    fbq.version = "2.0";
    fbq.push = fbq;
    w.fbq = fbq;
    addScript("https://connect.facebook.net/en_US/fbevents.js");
    fbq("set", "autoConfig", false, pixel); // no automatic reading of buttons or forms
    fbq("init", pixel);
  }
  const google = googleTagIds();
  if (google.length) {
    w.dataLayer = w.dataLayer || [];
    const dataLayer = w.dataLayer;
    w.gtag = function gtag() {
      // eslint-disable-next-line prefer-rest-params
      dataLayer.push(arguments);
    };
    addScript(`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(google[0])}`);
    w.gtag("js", new Date());
    for (const id of google) w.gtag("config", id, { send_page_view: false });
  }
}

export function trackPage(path: string): void {
  if (!loaded) return;
  const w = window as TrackingWindow;
  w.fbq?.("track", "PageView");
  w.gtag?.("event", "page_view", { page_path: path });
}

export function track(event: TrackEvent): void {
  if (!loaded) return;
  const w = window as TrackingWindow;
  w.fbq?.("track", META_EVENT[event]);
  w.gtag?.("event", GOOGLE_EVENT[event]);
}
