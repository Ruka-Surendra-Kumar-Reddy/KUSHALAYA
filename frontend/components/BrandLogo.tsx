"use client";

import { BRAND_ASSETS, BRAND_ASSET_SIZE, type BrandAssetVariant } from "@/lib/brand-assets";
import { BRAND_INLINE, BRAND_INLINE_SIZE, type BrandInlineVariant } from "@/lib/brand-inline";
import { publicBrandName, resolvePortalBrandTitle } from "@/lib/public-brand";
import { useBranding } from "./BrandingProvider";

/**
 * The logo is the first thing on the page, so it is loaded like it:
 * `fetchPriority="high"` lifts it above the images further down, and the
 * intrinsic `width`/`height` reserve its box so nothing reflows when it lands.
 * Never `loading="lazy"` — these marks are always above the fold.
 */
const eager = {
  fetchPriority: "high",
  decoding: "sync",
  loading: "eager",
} as const;

/**
 * The header and lockup marks ship inside the HTML as data URIs, so they paint
 * with the first frame instead of racing the JS chunks for bandwidth (nginx
 * 1.20 ignores HTTP/2 priorities, so on a slow link a separate request landed
 * ~1.5s after the page). The PWA icon is too large to inline and stays a URL.
 */
function markSource(variant: BrandAssetVariant) {
  if (variant in BRAND_INLINE) {
    const v = variant as BrandInlineVariant;
    return { src: BRAND_INLINE[v], size: BRAND_INLINE_SIZE[v], attrs: { decoding: "sync" } as const };
  }
  return { src: BRAND_ASSETS[variant], size: BRAND_ASSET_SIZE[variant], attrs: eager };
}

export function BrandLogo({
  className,
  variant = "header",
}: {
  className?: string;
  variant?: BrandAssetVariant;
}) {
  const branding = useBranding();
  const title =
    resolvePortalBrandTitle(branding.portal_title, branding.name) ||
    publicBrandName();
  // A tenant's own logo is an arbitrary file, so we cannot claim our
  // dimensions for it.
  const custom = branding.logo_url;
  const mark = markSource(variant);

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={custom || mark.src}
      alt={title}
      width={custom ? undefined : mark.size.width}
      height={custom ? undefined : mark.size.height}
      {...(custom ? eager : mark.attrs)}
      className={`brand-logo brand-logo-${variant} ${className || ""}`.trim()}
    />
  );
}

/** Logo that works on public pages without BrandingProvider. */
export function PublicBrandMark({
  variant = "header",
  className,
  alt,
}: {
  variant?: BrandAssetVariant;
  className?: string;
  alt?: string;
}) {
  const title = alt || publicBrandName();
  const mark = markSource(variant);
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={mark.src}
      alt={title}
      width={mark.size.width}
      height={mark.size.height}
      {...mark.attrs}
      className={`brand-logo brand-logo-${variant} ${className || ""}`.trim()}
    />
  );
}
