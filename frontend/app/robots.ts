import type { MetadataRoute } from "next";
import { headers } from "next/headers";

import { isMarketingHost } from "@/lib/hosts";
import { siteOrigin } from "@/lib/marketing/site-origin";

/**
 * /robots.txt per host. Only the public website (www) is crawlable; the ops
 * and family portals are private apps and ask every crawler to stay out.
 * The middleware passes any path with a "." straight through on every host,
 * so this one route answers for all of them.
 */
export const dynamic = "force-dynamic";

export default function robots(): MetadataRoute.Robots {
  const host = headers().get("host") || "";
  if (!isMarketingHost(host)) {
    return { rules: { userAgent: "*", disallow: "/" } };
  }
  return {
    // /marketing/<page> is the internal twin of each public page (kept out of
    // search), but the photos and share images live there too: allow image
    // files explicitly (the longer, more specific rule wins).
    rules: {
      userAgent: "*",
      allow: ["/", "/api/v1/public/blog/images/", "/marketing/*.webp", "/marketing/*.jpg", "/marketing/*.jpeg", "/marketing/*.png", "/marketing/*.svg"],
      disallow: ["/api/", "/marketing/"],
    },
    sitemap: `${siteOrigin(host)}/sitemap.xml`,
  };
}
