import { NextResponse, type NextRequest } from "next/server";
import { withPublicBrand } from "@/lib/public-brand";
import { BRAND_ASSETS, BRAND_ASSET_VERSION } from "@/lib/brand-assets";

/**
 * Web app manifest for the family portal PWA.
 *
 * Lives at a root path on purpose: Next only serves `app/manifest.*` as a
 * metadata route, so the old `app/kushalaya/family/manifest.ts` was never
 * served and installs fell back to browser defaults (a dark splash on
 * dark-mode phones). The family-host middleware passes any path containing a
 * dot straight through, so this URL works unchanged on both hosts, and the
 * start URL is chosen per host:
 *
 *   family.kushalaya.com  -> "/"                       (rewritten to the portal)
 *   ops.kushalaya.com     -> "/kushalaya/family/dashboard"
 *
 * Colours match the portal's white top bar so the install splash is light.
 */
export const dynamic = "force-dynamic";

function onFamilyHost(request: NextRequest): boolean {
  const host = (request.headers.get("host") || "").toLowerCase().split(":")[0];
  return host === "family.kushalaya.com" || host === "family.localhost";
}

export function GET(request: NextRequest) {
  const family = onFamilyHost(request);
  const manifest = {
    name: withPublicBrand("LiveWell360 Family"),
    short_name: "Family",
    description: withPublicBrand("LiveWell360 Safety Score, living plan, visits, and alerts for family members"),
    start_url: family ? "/dashboard" : "/kushalaya/family/dashboard",
    scope: family ? "/" : "/kushalaya/family/",
    display: "standalone",
    background_color: "#f3f6fa",
    theme_color: "#ffffff",
    orientation: "portrait",
    // /brand/* is served immutable for a year, so the URLs carry the asset
    // version: a new mark gets a new URL instead of a year-old cached one.
    icons: [
      { src: BRAND_ASSETS.icon, sizes: "512x512", type: "image/png", purpose: "any" },
      {
        src: `/brand/apple-touch-icon.png?v=${BRAND_ASSET_VERSION}`,
        sizes: "180x180",
        type: "image/png",
      },
    ],
  };
  return NextResponse.json(manifest, {
    headers: {
      "Content-Type": "application/manifest+json; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
