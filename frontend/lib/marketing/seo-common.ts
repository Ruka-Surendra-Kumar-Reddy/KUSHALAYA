/**
 * Shared bits for the SEO landing pages (/faq, /services/*, /elder-care/*).
 * Facts only: no offices, staff, partners, response times or statistics.
 */
import type { Metadata } from "next";

import { PUBLIC_PHONE } from "@/lib/public-brand";

import { PLAN_PRICE_LINE } from "./plans";
import { MARKETING_OG_IMAGE } from "./seo";

export const SEO_ORIGIN = "https://www.kushalaya.com";
export const SEO_BRAND = "KushAlaya";

export const SEO_PHONES = {
  india: { display: PUBLIC_PHONE.display, tel: PUBLIC_PHONE.tel },
  usCanada: { display: "+1 (678) 481-8252", tel: "tel:+16784818252" },
} as const;

/** The one price claim these pages make (owner-approved). */
export const SEO_PRICE_LINE = PLAN_PRICE_LINE;

/** Emergency wording used on every page that mentions SOS or emergencies. */
export const SEO_EMERGENCY_LINE =
  "In an emergency, call 112 (national emergency) or 108 (ambulance) first. KushAlaya is not an emergency service.";

export function seoMetadata(path: string, title: string, description: string): Metadata {
  const url = `${SEO_ORIGIN}${path}`;
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: { title, description, type: "website", url, siteName: SEO_BRAND, locale: "en_IN", images: [MARKETING_OG_IMAGE] },
    twitter: { card: "summary_large_image", title, description, images: [MARKETING_OG_IMAGE.url] },
    robots: { index: true, follow: true },
  };
}

/** The organisation as a provider in JSON-LD. Deliberately no address: we have no local offices. */
export const SEO_PROVIDER = {
  "@type": "Organization",
  name: SEO_BRAND,
  url: `${SEO_ORIGIN}/`,
  telephone: PUBLIC_PHONE.e164,
} as const;

export type SeoSection = { title: string; paras: readonly string[]; bullets?: readonly string[] };
