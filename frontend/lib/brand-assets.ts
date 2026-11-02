/** Static Kushalaya mark files in /public/brand. Internal vertical stays LIVEWELL360. */

/**
 * Cache-buster for the brand files.
 *
 * Files under `public/` are not content-hashed by Next, so out of the box they
 * ship as `Cache-Control: max-age=0` and the browser revalidates the logo on
 * *every* page load — a full round trip before it can paint, which is why the
 * logo used to appear a beat after the rest of the page. `next.config.mjs` now
 * serves `/brand/*` as immutable for a year; this version string is what makes
 * that safe, because a new logo gets a new URL instead of sitting behind a
 * year-old cache entry.
 *
 * **Bump this whenever a file in `public/brand` changes.** Same rule as the
 * `?v=` in the service-worker registrations.
 */
export const BRAND_ASSET_VERSION = "20261102";

const versioned = (path: string) => `${path}?v=${BRAND_ASSET_VERSION}`;

/**
 * Since 2026-09-29 all three are the SAME artwork — the square KushAlaya mark
 * (name arched over the emblem, transparent background) — rendered at three
 * sizes: `header` (192px) for page and portal bars, `lockup` (400px) for the
 * sign-in pages, loading and 404 screens, `icon` (512px) for the PWA. The old
 * wide 3.1:1 wordmark is gone at the owner's request ("the same logo
 * everywhere: big on sign-in, nominal elsewhere"), so no slot needs a
 * `<picture>` swap between marks any more.
 */
export const BRAND_ASSETS = {
  lockup: versioned("/brand/kushalaya-lockup.png"),
  icon: versioned("/brand/kushalaya-icon.png"),
  header: versioned("/brand/kushalaya-header.png"),
} as const;

export type BrandAssetVariant = keyof typeof BRAND_ASSETS;

/**
 * Intrinsic pixel sizes, rendered as `width`/`height` on every `<img>`.
 *
 * CSS sizes these logos by height, but without the attributes the browser has
 * no aspect ratio to reserve, so the row reflows when the image lands and the
 * late arrival is far more noticeable.
 *
 * **These must match the real files in `public/brand`.** Resizing an asset
 * without updating its entry here reserves the wrong box.
 */
export const BRAND_ASSET_SIZE: Record<BrandAssetVariant, { width: number; height: number }> = {
  // 320, not 400: it displays at 160px, so this is still 2x for sharp
  // screens, and it is inlined into every sign-in page — 400px blew the
  // 40,000-character budget in brand-inline.test.ts.
  lockup: { width: 320, height: 320 },
  icon: { width: 512, height: 512 },
  header: { width: 192, height: 192 },
};

/*
 * 2026-09-29b: regenerated from the owner's full-quality source (Downloads/
 * logo.jpeg, 803x854). The previous set had been flattened to ~204 colours and
 * the gradients on the hands and leaves were visibly banded; the source has
 * ~30,000. The source is a JPEG on white, so the background was matted out by
 * deriving alpha from whiteness and un-premultiplying the colour — a plain
 * cut-out leaves a pale fringe that is obvious on the navy ops sidebar.
 */
