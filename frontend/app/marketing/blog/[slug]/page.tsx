import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { BlogCardView } from "@/components/marketing/BlogCard";
import { BlogCta, BlogShare, BlogSideCard } from "@/components/marketing/BlogParts";
import { MarketingShell } from "@/components/marketing/MarketingShell";
import { MkLink as Link } from "@/components/marketing/MkLink";
import { Markdown } from "@/lib/blog/markdown";
import { fetchBlogPost } from "@/lib/blog/public";
import { BLOG_SITE, blogPostUrl, blogPostingLd, blogShareImage, breadcrumbLd, faqLd, ldJson } from "@/lib/blog/seo";
import { blogDate, blogImageSrc, readingLabel, tagLabel } from "@/lib/blog/text";
import { publicBrandName } from "@/lib/public-brand";
import "../blog.css";

/** ISR: an edited or newly published post shows within 5 minutes; publishing refreshes it at once. */
export const revalidate = 300;

type Props = { params: { slug: string } };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const post = await fetchBlogPost(params.slug);
  if (!post) return { title: `Article not found | ${publicBrandName()}`, robots: { index: false } };
  const title = post.seo_title || `${post.title} | ${publicBrandName()}`;
  const description = post.excerpt || undefined;
  const url = post.canonical_url || blogPostUrl(post.slug);
  const image = blogShareImage(post);
  const imageAlt = post.cover_image_alt || post.title;
  return {
    title: { absolute: title },
    description,
    alternates: { canonical: url },
    authors: post.author_name ? [{ name: post.author_name }] : undefined,
    keywords: post.tags,
    openGraph: {
      type: "article",
      title,
      description,
      url,
      siteName: publicBrandName(),
      locale: "en_IN",
      publishedTime: post.published_at || undefined,
      modifiedTime: post.updated_at || undefined,
      tags: post.tags,
      images: [{ url: image, alt: imageAlt }],
    },
    twitter: { card: "summary_large_image", title, description, images: [image] },
    robots: { index: true, follow: true },
  };
}

export default async function BlogArticlePage({ params }: Props) {
  const post = await fetchBlogPost(params.slug);
  if (!post) notFound();
  const brand = publicBrandName();
  const url = blogPostUrl(post.slug);
  const cover = blogImageSrc(post.cover_image_url);
  const ld: unknown[] = [
    blogPostingLd(post, brand),
    breadcrumbLd([
      { name: brand, url: `${BLOG_SITE}/` },
      { name: "Blog", url: `${BLOG_SITE}/blog` },
      { name: post.title, url },
    ]),
  ];
  if (post.faq?.length) ld.push(faqLd(post.faq));

  return (
    <MarketingShell>
      {ld.map((d, i) => (
        <script key={i} type="application/ld+json" dangerouslySetInnerHTML={{ __html: ldJson(d) }} />
      ))}
      <article className="mb-article">
        <header className="mb-article-head mk-wrap">
          {post.tags.length ? (
            <ul className="mb-article-tags" aria-label="Topics">
              {post.tags.map((t) => (
                <li key={t}>
                  <Link href={`/blog?tag=${encodeURIComponent(t)}`}>{tagLabel(t)}</Link>
                </li>
              ))}
            </ul>
          ) : null}
          <h1>{post.title}</h1>
          {post.excerpt ? <p className="mb-article-lede">{post.excerpt}</p> : null}
          <p className="mb-meta">
            {post.author_name ? <span>By {post.author_name}</span> : null}
            {post.author_name ? <span aria-hidden="true">·</span> : null}
            <time dateTime={post.published_at || undefined}>{blogDate(post.published_at)}</time>
            <span aria-hidden="true">·</span>
            <span>{readingLabel(post.reading_minutes)}</span>
          </p>
        </header>

        {cover ? (
          <figure className="mb-article-cover mk-wrap">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={cover} alt={post.cover_image_alt} width={1200} height={675} fetchPriority="high" decoding="async" />
          </figure>
        ) : null}

        <div className="mb-article-body mk-wrap">
          <div className="mb-article-main">
          <Markdown source={post.body_md} className="mb-prose" />

          {post.faq?.length ? (
            <section className="mb-faq" aria-labelledby="mb-faq-title">
              <h2 id="mb-faq-title">Questions families ask</h2>
              {post.faq.map((f) => (
                <details key={f.q}>
                  <summary>
                    <h3>{f.q}</h3>
                  </summary>
                  <Markdown source={f.a} className="mb-prose" />
                </details>
              ))}
            </section>
          ) : null}

          <BlogShare url={url} title={post.title} />
          <BlogCta title={post.title} />
          </div>
          <BlogSideCard title={post.title} />
        </div>
      </article>

      {post.related?.length ? (
        <section className="mb-related" aria-labelledby="mb-related-title">
          <div className="mk-wrap">
            <h2 id="mb-related-title">More from the blog</h2>
            <div className="mb-grid">
              {post.related.map((r) => (
                <BlogCardView key={r.id} post={r} headingLevel={3} />
              ))}
            </div>
          </div>
        </section>
      ) : null}
    </MarketingShell>
  );
}
