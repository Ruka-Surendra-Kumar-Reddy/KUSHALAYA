/**
 * Public-facing product brand (marketing, family portal, SEO, customer docs).
 * Internal vertical id stays LIVEWELL360 — only the display name is configurable.
 *
 * Env (build-time for Next.js):
 *   NEXT_PUBLIC_BRAND_NAME   default Kushalaya
 *   NEXT_PUBLIC_BRAND_MARK   short logo mark (default KU)
 *   NEXT_PUBLIC_BRAND_ACCENT optional logo accent suffix (default 360 when name ends with 360)
 */

export const DEFAULT_PUBLIC_BRAND_NAME = "KushAlaya";

/**
 * Registered legal entity, used in copyright lines and legal notices.
 * Unlike the product brand this is NOT configurable per tenant — it is the
 * company that owns the software.
 */
export const LEGAL_ENTITY_NAME = "KushAlaya Private Limited";

/** From the Certificate of Incorporation (22 Oct 2026). No GSTIN yet: show none. */
export const COMPANY_CIN = "U88100TS2026PTC224774";
/** GST registration (Telangana). Invoices also read it from Settings → Business. */
export const COMPANY_GSTIN = "36AANCK3491K1ZY";
export const COMPANY_INCORPORATED = "22 October 2026";
export const REGISTERED_ADDRESS =
  "Plot no. 65, H.No 2-17-8d, Dharmapuri Colony, Uppal, Beside SR Heights, Uppal, K.V. Rangareddy – 500039, Telangana, India";

/** The same registered office split for schema.org PostalAddress (JSON-LD). */
export const REGISTERED_ADDRESS_PARTS = {
  streetAddress: "Plot no. 65, H.No 2-17-8d, Dharmapuri Colony, Beside SR Heights, Uppal",
  addressLocality: "Hyderabad",
  addressRegion: "Telangana",
  postalCode: "500039",
  addressCountry: "IN",
} as const;

/**
 * The one public phone and email for the business: JSON-LD, SEO pages,
 * contact page and the footer fallback all read these.
 */
export const PUBLIC_PHONE = {
  display: "+91 905 905 1085",
  e164: "+919059051085",
  tel: "tel:+919059051085",
} as const;
export const PUBLIC_EMAIL = "contact@kushalaya.com";

/** Canonical token used in source copy; rewritten via withPublicBrand(). */
export const PUBLIC_BRAND_TOKEN = "LiveWell360";

/** Seeded / legacy portal titles that mean “product brand”, not a custom agency name. */
const PRODUCT_PORTAL_TITLE_ALIASES = new Set([
  "livewell360",
  "livewell 360",
  "livewell360™",
  "livewell 360™",
  "safehome360",
  "safehome 360",
  "safehome 360™",
  "safehome360™",
  "workforceos",
  "kushalaya",
]);

export function publicBrandName(): string {
  const fromEnv = (process.env.NEXT_PUBLIC_BRAND_NAME || "").trim();
  return fromEnv || DEFAULT_PUBLIC_BRAND_NAME;
}

/** Two–three letter mark for logos (e.g. LW). */
export function publicBrandMark(): string {
  const fromEnv = (process.env.NEXT_PUBLIC_BRAND_MARK || "").trim();
  if (fromEnv) return fromEnv.slice(0, 3).toUpperCase();
  const name = publicBrandName();
  if (name === DEFAULT_PUBLIC_BRAND_NAME) return "KU";
  const spaced = name
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/([A-Za-z])(\d)/g, "$1 $2")
    .replace(/[^A-Za-z0-9]+/g, " ")
    .trim();
  const parts = spaced.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  const compact = name.replace(/[^A-Za-z]/g, "");
  if (compact.length >= 2) return compact.slice(0, 2).toUpperCase();
  return "LW";
}

/** Styled suffix in the marketing logo (the "360" of a LiveWell360-style name). */
export function publicBrandAccent(): string {
  const fromEnv = (process.env.NEXT_PUBLIC_BRAND_ACCENT || "").trim();
  if (fromEnv) return fromEnv;
  const name = publicBrandName();
  if (name.endsWith("360")) return "360";
  return "";
}

export function publicBrandLogoParts(): { lead: string; accent: string } {
  const name = publicBrandName();
  const accent = publicBrandAccent();
  if (accent && name.endsWith(accent)) {
    return { lead: name.slice(0, -accent.length), accent };
  }
  return { lead: name, accent: "" };
}

function normalizeBrandAlias(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[®©]/g, "")
    .replace(/\u2122/g, "™")
    .replace(/\s+/g, " ");
}

/** True when the title is the product brand (not a custom agency portal name). */
export function isProductPortalTitle(title: string | null | undefined): boolean {
  if (!title?.trim()) return true;
  return PRODUCT_PORTAL_TITLE_ALIASES.has(normalizeBrandAlias(title));
}

/**
 * Sidebar / shell title: use configured public brand for product aliases,
 * otherwise keep a custom tenant portal title (still rewriting LiveWell360 tokens).
 */
export function resolvePortalBrandTitle(
  portalTitle?: string | null,
  fallbackName?: string | null,
): string {
  const raw = (portalTitle || fallbackName || "").trim();
  if (isProductPortalTitle(raw)) return publicBrandName();
  return withPublicBrand(raw);
}

/** Rewrite authored LiveWell360 copy to the configured public brand. */
export function withPublicBrand(text: string): string {
  const brand = publicBrandName();
  let out = text;
  // Prefer trademarked form first so we don't leave a stray ™ after replacement.
  if (brand !== `${PUBLIC_BRAND_TOKEN}™`) {
    out = out.split(`${PUBLIC_BRAND_TOKEN}™`).join(brand);
  }
  if (brand !== PUBLIC_BRAND_TOKEN) {
    out = out.split(PUBLIC_BRAND_TOKEN).join(brand);
  }
  return out;
}

/** Customer-facing name of the 0–100 home score (was "Independence Score™"). */
export function publicSafetyScoreName(): string {
  return `${publicBrandName()} Safety Score`;
}

export function publicBrandFamilyLabel(): string {
  return withPublicBrand("LiveWell360 Family");
}

export function publicBrandOpsLabel(): string {
  return withPublicBrand("LiveWell360 operations");
}
