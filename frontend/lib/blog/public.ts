/** Public blog reads for server components on www (no auth, ISR-cached). */
import type { BlogList, BlogPublicPost } from "./api";

/* --- Public reads (server components on www) -------------------------------- */

/** Seconds a public blog page is cached before Next fetches it again (ISR). */
export const BLOG_REVALIDATE = 300;

/** Server-side API base: the VM's local API when set, else the public API URL. */
function serverApiBase(): string {
  return (process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8010").replace(/\/$/, "");
}

async function publicGet<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${serverApiBase()}/api/v1/public/blog${path}`, {
      next: { revalidate: BLOG_REVALIDATE, tags: ["blog"] },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    // A public page never 500s because the API is briefly down.
    return null;
  }
}

export function fetchBlogList(page = 1, tag?: string | null): Promise<BlogList | null> {
  const q = new URLSearchParams({ page: String(page), per_page: "9" });
  if (tag) q.set("tag", tag);
  return publicGet<BlogList>(`/posts?${q}`);
}

export const fetchBlogPost = (slug: string) => publicGet<BlogPublicPost>(`/posts/${encodeURIComponent(slug)}`);

export const fetchBlogSitemap = () =>
  publicGet<{ slug: string; updated_at: string | null; published_at: string | null }[]>("/sitemap");
