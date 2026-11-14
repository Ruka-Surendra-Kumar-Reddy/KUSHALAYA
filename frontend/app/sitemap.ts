import type { MetadataRoute } from "next";
import { headers } from "next/headers";

import { isMarketingHost } from "@/lib/hosts";
import { siteOrigin } from "@/lib/marketing/site-origin";
import { fetchBlogSitemap } from "@/lib/blog/public";
import { SEO_CITIES } from "@/lib/marketing/seo-cities";
import { SEO_SERVICES } from "@/lib/marketing/seo-services";

/** Public pages of the www site. Ops / family hosts get an empty sitemap. */
export const dynamic = "force-dynamic";

const PAGES: { path: string; priority: number }[] = [
  { path: "/", priority: 1 },
  { path: "/packages", priority: 0.9 },
  { path: "/kushcare-discovery", priority: 0.9 },
  { path: "/kushlife", priority: 0.7 },
  { path: "/safe-homes", priority: 0.7 },
  { path: "/contact", priority: 0.7 },
  { path: "/blog", priority: 0.7 },
  { path: "/about", priority: 0.6 },
  { path: "/faq", priority: 0.6 },
  { path: "/services", priority: 0.8 },
  ...SEO_SERVICES.map((s) => ({ path: `/services/${s.slug}`, priority: 0.7 })),
  ...SEO_CITIES.map((c) => ({ path: `/elder-care/${c.slug}`, priority: 0.6 })),
  { path: "/founder", priority: 0.5 },
  { path: "/partners", priority: 0.4 },
  { path: "/become-a-partner", priority: 0.4 },
  { path: "/vision", priority: 0.3 },
  { path: "/brochure", priority: 0.3 },
  { path: "/privacy", priority: 0.2 },
  { path: "/terms", priority: 0.2 },
  { path: "/refund-policy", priority: 0.2 },
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const host = headers().get("host") || "";
  if (!isMarketingHost(host)) return [];
  const origin = siteOrigin(host);
  const pages: MetadataRoute.Sitemap = PAGES.map((p) => ({
    url: `${origin}${p.path === "/" ? "/" : p.path}`,
    changeFrequency: "monthly",
    priority: p.priority,
  }));
  // Published blog posts (lastmod = last edit). An API hiccup just leaves them out this time.
  const posts = (await fetchBlogSitemap()) || [];
  return [
    ...pages,
    ...posts.map((p) => ({
      url: `${origin}/blog/${p.slug}`,
      lastModified: p.updated_at || p.published_at || undefined,
      changeFrequency: "monthly" as const,
      priority: 0.6,
    })),
  ];
}
