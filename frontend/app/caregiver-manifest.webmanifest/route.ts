import { NextResponse } from "next/server";
import { BRAND_ASSETS, BRAND_ASSET_VERSION } from "@/lib/brand-assets";

/**
 * Web app manifest for the caregiver field app (caregiver.kushalaya.com/caregiver,
 * also ops.kushalaya.com/caregiver). A root path for the same reason as
 * app/family-manifest.webmanifest: Next serves `app/manifest.*` only at the root.
 */
export const dynamic = "force-static";

export function GET() {
  const manifest = {
    name: "KushAlaya Caregiver",
    short_name: "Caregiver",
    description: "Today's visits, KushLife checks, photos and emergencies for KushAlaya caregivers",
    start_url: "/caregiver",
    // Only the field app; sign-in and other pages open outside the installed app.
    scope: "/caregiver",
    display: "standalone",
    background_color: "#f3f6fa",
    theme_color: "#0e2a4f",
    orientation: "portrait",
    icons: [
      { src: `/brand/kushalaya-icon-192.png?v=${BRAND_ASSET_VERSION}`, sizes: "192x192", type: "image/png", purpose: "any" },
      { src: BRAND_ASSETS.icon, sizes: "512x512", type: "image/png", purpose: "any" },
      { src: `/brand/apple-touch-icon.png?v=${BRAND_ASSET_VERSION}`, sizes: "180x180", type: "image/png" },
    ],
  };
  return NextResponse.json(manifest, {
    headers: { "Content-Type": "application/manifest+json; charset=utf-8", "Cache-Control": "public, max-age=3600" },
  });
}
