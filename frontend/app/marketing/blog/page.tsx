import type { Metadata } from "next";

import { MarketingShell } from "@/components/marketing/MarketingShell";
import { MkLink as Link } from "@/components/marketing/MkLink";
import { fetchBlogList } from "@/lib/blog/public";
import { BlogCardView } from "@/components/marketing/BlogCard";
import { BLOG_SITE, breadcrumbLd, ldJson } from "@/lib/blog/seo";
import { tagLabel } from "@/lib/blog/text";
import { MARKETING_OG_IMAGE } from "@/lib/marketing/seo";
import { publicBrandName } from "@/lib/public-brand";
import "./blog.css";

/** New posts appear within 5 minutes without a rebuild (publishing also refreshes it at once). */
export const revalidate = 300;

const title = `Elder Care Blog: Guides for Indian Families | ${publicBrandName()}`;
const description =
  "Practical guides on caring for ageing parents in India — home safety, falls, KushLife visits and staying close when you live far away.";

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: `${BLOG_SITE}/blog` },
  openGraph: { title, description, type: "website", url: `${BLOG_SITE}/blog`, images: [MARKETING_OG_IMAGE] },
  twitter: { card: "summary_large_image", title, description, images: [MARKETING_OG_IMAGE.url] },
  robots: { index: true, follow: true },
};

function pageHref(page: number, tag: string | null) {
  const q = new URLSearchParams();
  if (tag) q.set("tag", tag);
  if (page > 1) q.set("page", String(page));
  const s = q.toString();
  return `/blog${s ? `?${s}` : ""}`;
}

export default async function BlogIndexPage({ searchParams }: { searchParams: { page?: string; tag?: string } }) {
  const page = Math.max(1, Math.min(1000, Number.parseInt(searchParams.page || "1", 10) || 1));
  const tag = (searchParams.tag || "").trim().toLowerCase().slice(0, 40) || null;
  const data = await fetchBlogList(page, tag);
  const items = data?.items || [];
  const brand = publicBrandName();

  return (
    <MarketingShell>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: ldJson(breadcrumbLd([{ name: brand, url: `${BLOG_SITE}/` }, { name: "Blog", url: `${BLOG_SITE}/blog` }])),
        }}
      />
      <section className="mb-hero">
        <div className="mk-wrap">
          <p className="mk-eyebrow">{brand} blog</p>
          <h1>Caring for ageing parents, one practical guide at a time</h1>
          <p className="mk-lede">
            Plain-English advice for families across India and those caring from far away: safer homes, fewer falls,
            and how to stay close to your parents&apos; everyday life.
          </p>
          {data?.tags.length ? (
            <nav className="mb-tags" aria-label="Topics">
              <Link className={!tag ? "is-on" : undefined} href="/blog">
                All
              </Link>
              {data.tags.map((t) => (
                <Link key={t} className={t === tag ? "is-on" : undefined} href={pageHref(1, t)}>
                  {tagLabel(t)}
                </Link>
              ))}
            </nav>
          ) : null}
        </div>
      </section>

      <section className="mb-list" aria-label="Articles">
        <div className="mk-wrap">
          {items.length === 0 ? (
            <p className="mb-empty">
              {data === null ? "The articles could not be loaded just now. Please try again in a minute." : "No articles here yet."}
            </p>
          ) : (
            <div className="mb-grid">
              {items.map((p, i) => (
                <BlogCardView key={p.id} post={p} eager={i < 2} />
              ))}
            </div>
          )}
          {data && data.pages > 1 ? (
            <nav className="mb-pages" aria-label="Pages">
              {page > 1 ? (
                <Link href={pageHref(page - 1, tag)} rel="prev">
                  ← Newer
                </Link>
              ) : (
                <span />
              )}
              <span>
                Page {data.page} of {data.pages}
              </span>
              {page < data.pages ? (
                <Link href={pageHref(page + 1, tag)} rel="next">
                  Older →
                </Link>
              ) : (
                <span />
              )}
            </nav>
          ) : null}
        </div>
      </section>
    </MarketingShell>
  );
}
