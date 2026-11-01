/**
 * Deep-replace the LiveWell360 authoring token with the configured public brand.
 * Used for i18n catalogs and nested marketing copy objects.
 */
import {
  publicBrandName,
  PUBLIC_BRAND_TOKEN,
  withPublicBrand,
} from "./public-brand";

export function brandifyDeep<T>(value: T): T {
  if (typeof value === "string") return withPublicBrand(value) as T;
  if (Array.isArray(value)) return value.map((v) => brandifyDeep(v)) as T;
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = brandifyDeep(v);
    }
    return out as T;
  }
  return value;
}

export {
  DEFAULT_PUBLIC_BRAND_NAME,
  PUBLIC_BRAND_TOKEN,
  publicBrandAccent,
  publicBrandFamilyLabel,
  publicBrandLogoParts,
  publicBrandMark,
  publicBrandName,
  publicBrandOpsLabel,
  withPublicBrand,
} from "./public-brand";
