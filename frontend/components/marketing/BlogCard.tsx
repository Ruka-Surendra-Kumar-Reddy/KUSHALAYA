import type { BlogCard } from "@/lib/blog/api";
import { blogDate, blogImageSrc, readingLabel, tagLabel } from "@/lib/blog/text";
import { MkLink as Link } from "./MkLink";

/** A post card for /blog and "Related articles". headingLevel keeps one h1 per page and a sane outline. */
export function BlogCardView({ post, eager = false, headingLevel = 2 }: { post: BlogCard; eager?: boolean; headingLevel?: 2 | 3 }) {
  const H = headingLevel === 3 ? "h3" : "h2";
  const cover = blogImageSrc(post.cover_image_url);
  return (
    <article className="mb-card">
      <Link className="mb-card-link" href={`/blog/${post.slug}`}>
        {cover ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            className="mb-card-img"
            src={cover}
            alt={post.cover_image_alt}
            width={1200}
            height={675}
            loading={eager ? "eager" : "lazy"}
            decoding="async"
          />
        ) : (
          <span className="mb-card-img mb-card-img--empty" aria-hidden="true" />
        )}
        <div className="mb-card-body">
          {post.tags.length ? <span className="mb-card-tag">{tagLabel(post.tags[0])}</span> : null}
          <H className="mb-card-title">{post.title}</H>
          {post.excerpt ? <p className="mb-card-excerpt">{post.excerpt}</p> : null}
          <span className="mb-meta">
            <time dateTime={post.published_at || undefined}>{blogDate(post.published_at)}</time>
            <span aria-hidden="true">·</span>
            <span>{readingLabel(post.reading_minutes)}</span>
          </span>
        </div>
      </Link>
    </article>
  );
}
