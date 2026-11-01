"use client";

import { useEffect, useState } from "react";

import { getApiUrl } from "@/lib/api";
import { HOME_ASSESSMENT, inr } from "@/lib/care-plan-catalog";
import { FOUNDER } from "@/lib/marketing/founder";
import { LEGAL_ENTITY_NAME, REGISTERED_ADDRESS } from "@/lib/public-brand";

/**
 * Website settings the public pages read (Settings → Website, FIX 107/108):
 * care-team WhatsApp, assessment price, trial banner, real testimonials and
 * company details. Every field has a safe fallback, so the site renders the
 * same whether or not the API answers.
 */
export type SiteConfig = {
  whatsapp: string;
  whatsapp_link: string;
  whatsapp_is_default: boolean;
  phone: string;
  phone_tel: string;
  city: string;
  areas: string[];
  assessment_price_paise: number | null;
  assessment_price_label: string;
  assessment_is_paid: boolean;
  slot_windows: string[];
  trial: { enabled: boolean; text: string };
  testimonials: { quote: string; name: string; place: string }[];
  company: {
    legal_name: string;
    address: string;
    gstin: string;
    grievance_name: string;
    grievance_email: string;
    grievance_phone: string;
  };
};

const founderDigits = FOUNDER.phoneTel.replace(/\D/g, "");

export const SITE_FALLBACK: SiteConfig = {
  whatsapp: FOUNDER.phoneDisplay,
  whatsapp_link: `https://wa.me/${founderDigits}`,
  whatsapp_is_default: true,
  phone: FOUNDER.phoneDisplay,
  phone_tel: `+${founderDigits}`,
  city: "Hyderabad",
  areas: [],
  // KushCare Discovery home assessment: free unless Ops sets a price (owner, 27 Oct 2026).
  assessment_price_paise: HOME_ASSESSMENT.pricePaise || null,
  assessment_price_label: HOME_ASSESSMENT.pricePaise ? inr(HOME_ASSESSMENT.pricePaise) : "Free",
  assessment_is_paid: HOME_ASSESSMENT.pricePaise > 0,
  slot_windows: ["morning", "afternoon", "evening"],
  trial: { enabled: false, text: "" },
  testimonials: [],
  company: {
    legal_name: LEGAL_ENTITY_NAME,
    address: REGISTERED_ADDRESS,
    gstin: "",
    grievance_name: "",
    grievance_email: "",
    grievance_phone: "",
  },
};

/** The care team's call-back promise, stated once. */
export const CALLBACK_PROMISE = "We call you back within 2 hours";

/**
 * Care-team hours, shown on /contact with the times for families abroad.
 * 8 am–9 pm IST (UTC+5:30). OWNER TO CONFIRM before relying on it.
 */
/** Hidden on the site until the owner confirms real hours (set SHOW_SUPPORT_HOURS = true). */
export const SHOW_SUPPORT_HOURS = false;

export const SUPPORT_HOURS = {
  ist: "8 am – 9 pm IST, every day",
  us: "US Eastern: 10:30 pm – 11:30 am (9:30 pm – 10:30 am in winter)",
  uk: "UK: 3:30 am – 4:30 pm (2:30 am – 3:30 pm in winter)",
} as const;

let cache: SiteConfig | null = null;
let inflight: Promise<SiteConfig> | null = null;

export function loadSiteConfig(): Promise<SiteConfig> {
  if (cache) return Promise.resolve(cache);
  if (!inflight) {
    // Only a real answer is cached. A failed or odd reply returns the fallback
    // for now and clears `inflight`, so the next page (or remount) tries again.
    inflight = fetch(`${getApiUrl()}/api/v1/home-safety/enquiries/site`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d && typeof d.whatsapp_link === "string") {
          cache = { ...SITE_FALLBACK, ...d, company: withCompanyFallback(d.company) } as SiteConfig;
          return cache;
        }
        inflight = null;
        return SITE_FALLBACK;
      })
      .catch(() => {
        inflight = null;
        return SITE_FALLBACK;
      });
  }
  return inflight;
}

/** Company block from the API, with the registered name and address where it is blank. */
export function withCompanyFallback(company: Partial<SiteConfig["company"]> | null | undefined): SiteConfig["company"] {
  const out = { ...SITE_FALLBACK.company };
  for (const [k, v] of Object.entries(company || {})) {
    if (typeof v === "string" && v.trim() && k in out) out[k as keyof SiteConfig["company"]] = v;
  }
  return out;
}

/** Test helper: forget the cached answer. */
export function resetSiteConfigCache(): void {
  cache = null;
  inflight = null;
}

/**
 * Wording for the KushCare Discovery home visit price. While it is free:
 * "Free"; once a price is set: the price label (e.g. "₹499"). `neutral` is a
 * call to action that never promises "free" when a price exists.
 */
export function assessmentWording(cfg: Pick<SiteConfig, "assessment_is_paid" | "assessment_price_label">): {
  isFree: boolean;
  /** "Free" or "₹499". */
  price: string;
  /** "Free home assessment" or "Home assessment · ₹499". */
  visit: string;
} {
  const isFree = !cfg.assessment_is_paid;
  const price = isFree ? "Free" : cfg.assessment_price_label;
  return { isFree, price, visit: isFree ? "Free home assessment" : `Home assessment · ${price}` };
}

/** Site settings; the fallback until (or unless) the API answers. */
export function useSiteConfig(): SiteConfig {
  const [cfg, setCfg] = useState<SiteConfig>(cache ?? SITE_FALLBACK);
  useEffect(() => {
    let live = true;
    void loadSiteConfig().then((c) => {
      if (live) setCfg(c);
    });
    return () => {
      live = false;
    };
  }, []);
  return cfg;
}

/** wa.me link with a prefilled first message. */
export function whatsAppHref(cfg: Pick<SiteConfig, "whatsapp_link">, text?: string): string {
  return text ? `${cfg.whatsapp_link}?text=${encodeURIComponent(text)}` : cfg.whatsapp_link;
}

// --- Lead tracking: first touch UTM / referrer / landing page / referral --------

const LEAD_KEY = "kushalaya-lead";

export type LeadTouch = {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  referrer?: string;
  landing_page?: string;
  ref?: string;
  /** Channel from ?src= (e.g. "qr" on printed standees); allow-listed, matches the backend. */
  src?: string;
};

/** ?src= values we keep; anything else is dropped (the backend falls back to "website"). */
export const LEAD_SRC_ALLOWED = ["website", "qr", "whatsapp", "google", "referral", "direct"] as const;

/** Pure: build the first-touch record from a URL and document.referrer. */
export function leadFromUrl(href: string, referrer: string): LeadTouch {
  const url = new URL(href);
  const q = url.searchParams;
  const out: LeadTouch = {};
  for (const k of ["utm_source", "utm_medium", "utm_campaign"] as const) {
    const v = (q.get(k) || "").trim();
    if (v) out[k] = v.slice(0, 150);
  }
  const ref = (q.get("ref") || "").trim();
  if (/^[0-9A-Za-z]{6,20}$/.test(ref)) out.ref = ref.toUpperCase();
  const src = (q.get("src") || "").trim().toLowerCase();
  if ((LEAD_SRC_ALLOWED as readonly string[]).includes(src)) out.src = src;
  // Our own pages are not a referrer.
  if (referrer && !/kushalaya\.com|localhost/i.test(new URL(referrer, href).hostname)) {
    out.referrer = referrer.slice(0, 500);
  }
  out.landing_page = (url.pathname + url.search).slice(0, 500);
  return out;
}

/** Keep the first touch for the visit; a referral code or new campaign later still wins. */
export function captureLead(): void {
  if (typeof window === "undefined") return;
  try {
    const now = leadFromUrl(window.location.href, document.referrer || "");
    const prev = readLead();
    const hasNew = Boolean(now.utm_source || now.ref || now.src);
    if (prev.landing_page && !hasNew) return;
    const merged = hasNew ? { ...prev, ...now } : { ...now, ...prev };
    window.sessionStorage.setItem(LEAD_KEY, JSON.stringify(merged));
  } catch {
    /* storage blocked: the enquiry simply goes without tracking */
  }
}

export function readLead(): LeadTouch {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.sessionStorage.getItem(LEAD_KEY);
    return raw ? (JSON.parse(raw) as LeadTouch) : {};
  } catch {
    return {};
  }
}
