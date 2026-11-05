import { PUBLIC_EMAIL, publicBrandName, withPublicBrand } from "@/lib/public-brand";
/** Public family marketing contact CTAs (www.kushalaya.com). */

/**
 * Branded KushCare Discovery page on www.kushalaya.com (embeds the Google Form).
 * Override only if you need a temporary external redirect.
 */
export const PARENT_CARE_CHECK_HREF =
  (process.env.NEXT_PUBLIC_PARENT_CARE_CHECK_URL || "").trim() || "/kushcare-discovery";

/**
 * Google Forms embed src (long docs.google.com URL with ?embedded=true).
 * Short forms.gle links do not embed correctly.
 */
export const PARENT_CARE_CHECK_FORM_EMBED_SRC =
  (process.env.NEXT_PUBLIC_PARENT_CARE_CHECK_EMBED_URL || "").trim() ||
  "https://docs.google.com/forms/d/e/1FAIpQLSeQjLpuzdIvkIPEIizSdkDn5SSS-ZD2_PkS_hjHAdsZL_V4Ww/viewform?embedded=true";

export function familyWhatsAppDigits(): string {
  return (process.env.NEXT_PUBLIC_FAMILY_WHATSAPP || "").replace(/\D/g, "");
}

export function familyPhoneDisplay(): string {
  return (process.env.NEXT_PUBLIC_FAMILY_PHONE || "").trim();
}

export function familyPhoneTelHref(): string {
  const raw = familyPhoneDisplay() || familyWhatsAppDigits();
  if (!raw) return PARENT_CARE_CHECK_HREF;
  const digits = raw.replace(/[^\d+]/g, "");
  return digits ? `tel:${digits}` : PARENT_CARE_CHECK_HREF;
}

/** True when the href opens an external form / wa.me (use target=_blank). */
export function isExternalFamilyContactHref(href: string): boolean {
  return /^https?:\/\//i.test(href);
}

/**
 * Primary family contact CTA. Prefers WhatsApp when configured;
 * otherwise opens the KushCare Discovery page / form.
 */
export function familyWhatsAppHref(prefill?: string): string {
  const digits = familyWhatsAppDigits();
  if (!digits) return PARENT_CARE_CHECK_HREF;
  const text = encodeURIComponent(
    prefill ||
      withPublicBrand("Hi LiveWell360 — I'd like to book a home safety assessment for my family."),
  );
  return `https://wa.me/${digits}?text=${text}`;
}

export function partnerWhatsAppHref(prefill?: string): string {
  return familyWhatsAppHref(
    prefill ||
      withPublicBrand("Hi LiveWell360 — I'm interested in joining the Trusted Partner Network as a supplier or installer."),
  );
}

export function familyContactsConfigured(): boolean {
  return Boolean(familyWhatsAppDigits() || familyPhoneDisplay());
}

export const FAMILY_PORTAL_LOGIN =
  process.env.NEXT_PUBLIC_FAMILY_PORTAL_URL ||
  "https://family.kushalaya.com/login";

/** Staff / operations portal sign-in. */
export const OPS_PORTAL_LOGIN =
  process.env.NEXT_PUBLIC_OPS_PORTAL_URL || "https://ops.kushalaya.com/login";

/** Public website. The test system sets this so its links stay on test. */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "https://www.kushalaya.com").replace(/\/$/, "");
export const SITE_HOST = new URL(SITE_URL).host;
export const FAMILY_PORTAL_HOST = new URL(FAMILY_PORTAL_LOGIN).host;

/** Clean public paths (rewritten to /marketing/... on www.kushalaya.com). */
export const PARTNERS_HREF = "/partners";
export const BECOME_A_PARTNER_HREF = "/become-a-partner";
export const PACKAGES_HREF = "/packages";
export const SAFE_HOMES_HREF = "/safe-homes";
/** Was "Parent Care Check" at /parent-care-check (still redirects — printed QR codes use it). */
export const PARENT_CARE_CHECK_PATH = "/kushcare-discovery";
/** Printable one-page vision sheet */
export const VISION_HREF = "/vision";
/** Printable simple brochure */
export const BROCHURE_HREF = "/brochure";
export const BROCHURE_PDF_HREF = "/marketing/kushalaya-brochure.pdf";
/** Founder page and contact page (clean public paths). */
export const FOUNDER_HREF = "/founder";
export const CONTACT_HREF = "/contact";
export const ABOUT_HREF = "/about";
/** Legal pages (footer). */
export const PRIVACY_HREF = "/privacy";
export const TERMS_HREF = "/terms";
export const REFUND_HREF = "/refund-policy";

/** Number for families calling from the US and Canada (owner, 11 Oct 2026). */
export const US_PHONE = { display: "+1 (678) 481-8252", tel: "tel:+16784818252" } as const;

/** Company mailboxes. Use the one that matches the reader's purpose. */
export const EMAILS = {
  /** Families and general enquiries — the default. */
  contact: PUBLIC_EMAIL,
  /** Plans, pricing, partnerships and business enquiries. */
  sales: "sales@kushalaya.com",
  /** General information, printables, press. */
  info: "info@kushalaya.com",
} as const;

export function mailtoHref(email: string, subject?: string): string {
  return subject ? `mailto:${email}?subject=${encodeURIComponent(subject)}` : `mailto:${email}`;
}
