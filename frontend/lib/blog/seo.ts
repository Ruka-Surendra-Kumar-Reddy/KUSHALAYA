/** Structured data and absolute URLs for www /blog pages. */
import type { BlogPublicPost } from "./api";
import { MARKETING_OG_IMAGE } from "@/lib/marketing/seo";

export const BLOG_SITE = "https://www.kushalaya.com";

/** Site paths (/marketing/…, /api/…) as absolute www URLs — www proxies /api to the backend. */
export function absUrl(url?: string | null): string {
  const u = (url || "").trim();
  if (!u) return "";
  if (/^https?:\/\//i.test(u)) return u;
  return u.startsWith("/") && !u.startsWith("//") ? `${BLOG_SITE}${u}` : "";
}

export const blogPostUrl = (slug: string) => `${BLOG_SITE}/blog/${slug}`;

export function blogShareImage(p: Pick<BlogPublicPost, "og_image_url" | "cover_image_url">): string {
  return absUrl(p.og_image_url) || absUrl(p.cover_image_url) || MARKETING_OG_IMAGE.url;
}

/** Strip Markdown link syntax for plain-text JSON-LD answers. */
const plain = (md: string) => md.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/[*_`#>]/g, "").trim();

export function blogPostingLd(p: BlogPublicPost, brand: string) {
  const url = p.canonical_url || blogPostUrl(p.slug);
  return {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: p.title.slice(0, 110),
    description: p.excerpt || undefined,
    image: [blogShareImage(p)],
    datePublished: p.published_at || undefined,
    dateModified: p.updated_at || p.published_at || undefined,
    author: p.author_name ? { "@type": "Organization", name: p.author_name, url: BLOG_SITE } : { "@type": "Organization", name: brand, url: BLOG_SITE },
    publisher: { "@type": "Organization", name: brand, url: BLOG_SITE, logo: { "@type": "ImageObject", url: `${BLOG_SITE}/brand/kushalaya-icon-512.png` } },
    mainEntityOfPage: { "@type": "WebPage", "@id": url },
    keywords: p.tags?.length ? p.tags.join(", ") : undefined,
    url,
  };
}

export function breadcrumbLd(items: { name: string; url: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((it, i) => ({ "@type": "ListItem", position: i + 1, name: it.name, item: it.url })),
  };
}

export function faqLd(faq: { q: string; a: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faq.map((f) => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: plain(f.a) } })),
  };
}

/** JSON for a <script type="application/ld+json">, with "<" escaped so it can never close the tag. */
export function ldJson(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
