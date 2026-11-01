"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Flash } from "@/components/Flash";
import { PageHeader } from "@/components/PageHeader";
import { listBlogPosts, type BlogAdminPost } from "@/lib/blog/api";
import { blogDate, blogImageSrc } from "@/lib/blog/text";
import { isAdmin as isAdminUser } from "@/lib/roles";
import "@/components/ops/blog.css";

/** What the list shows in the Status column. A scheduled post whose time has passed is live. */
function statusLabel(p: Pick<BlogAdminPost, "status" | "live">): { text: string; tone: string } {
  if (p.status === "published") return { text: "Published", tone: "live" };
  if (p.status === "scheduled") return p.live ? { text: "Published", tone: "live" } : { text: "Scheduled", tone: "soon" };
  return { text: "Draft", tone: "draft" };
}

const FILTERS = [
  { key: "all", label: "All" },
  { key: "live", label: "Published" },
  { key: "soon", label: "Scheduled" },
  { key: "draft", label: "Drafts" },
] as const;
type FilterKey = (typeof FILTERS)[number]["key"];

/** Blog (Growth): admins write the posts shown on www /blog. */
export default function BlogListPage() {
  const isAdmin = isAdminUser();
  const router = useRouter();
  const [posts, setPosts] = useState<BlogAdminPost[] | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<FilterKey>("all");

  useEffect(() => {
    if (!isAdmin) {
      router.replace("/unauthorized");
      return;
    }
    listBlogPosts()
      .then(setPosts)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [isAdmin, router]);

  if (!isAdmin) return null;
  return (
    <>
      <div className="ks-head-row">
        <PageHeader title="Blog" subtitle="Articles on kushalaya.com/blog — drafts stay private" />
        <div className="ks-head-actions">
          <button type="button" onClick={() => router.push("/kushalaya/blog/new")} aria-label="New post" title="New post">
            <span className="ks-ha-icon" aria-hidden="true">+</span>
            <span className="ks-ha-label">+ New post</span>
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => window.open("/marketing/blog", "_blank", "noopener,noreferrer")}
            aria-label="View the blog (opens in a new tab)"
            title="View the blog"
          >
            <span className="ks-ha-icon" aria-hidden="true">↗</span>
            <span className="ks-ha-label">View blog ↗</span>
          </button>
        </div>
      </div>
      <Flash error={error} message="" onClear={() => setError("")} />
      {posts === null ? (
        <div className="card">
          <p className="muted">Loading…</p>
        </div>
      ) : posts.length === 0 ? (
        <div className="card bl-empty">
          <h2>No posts yet</h2>
          <p className="muted">Write your first article for www.kushalaya.com/blog.</p>
          <Link className="bl-linkbtn" href="/kushalaya/blog/new">
            + Write a post
          </Link>
        </div>
      ) : (
        <>
          <div className="bl-filters" role="group" aria-label="Show">
            {FILTERS.map((f) => {
              const n = posts.filter((p) => f.key === "all" || statusLabel(p).tone === f.key).length;
              if (f.key !== "all" && !n) return null;
              return (
                <button key={f.key} type="button" aria-pressed={filter === f.key} className={filter === f.key ? "is-on" : ""} onClick={() => setFilter(f.key)}>
                  {f.label} <span>{n}</span>
                </button>
              );
            })}
          </div>
          <ul className="bl-list">
            {posts
              .filter((p) => filter === "all" || statusLabel(p).tone === filter)
              .map((p) => {
                const s = statusLabel(p);
                const date = p.status === "scheduled" ? p.publish_at : p.published_at || p.updated_at;
                const edit = `/kushalaya/blog/${p.id}`;
                return (
                  <li key={p.id} className="card bl-item">
                    <Link className="bl-item-thumb" href={edit} tabIndex={-1} aria-hidden="true">
                      {p.cover_image_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={blogImageSrc(p.cover_image_url)} alt="" loading="lazy" />
                      ) : (
                        <span>No cover</span>
                      )}
                    </Link>
                    <div className="bl-item-body">
                      <div className="bl-item-meta">
                        <span className={`bl-status bl-status--${s.tone}`}>{s.text}</span>
                        <span>
                          {p.status === "draft" ? "Edited " : p.status === "scheduled" && !p.live ? "Goes live " : ""}
                          {blogDate(date)}
                        </span>
                      </div>
                      <Link className="bl-title-link" href={edit}>
                        {p.title || "Untitled post"}
                      </Link>
                      {p.excerpt ? <p className="bl-item-excerpt">{p.excerpt}</p> : null}
                    </div>
                    <div className="bl-item-actions">
                      <Link className="bl-linkbtn bl-linkbtn--ghost" href={edit}>
                        Edit
                      </Link>
                      {p.live ? (
                        <a className="bl-linkbtn bl-linkbtn--ghost" href={`/marketing/blog/${p.slug}`} target="_blank" rel="noopener noreferrer">
                          View ↗
                        </a>
                      ) : null}
                    </div>
                  </li>
                );
              })}
          </ul>
        </>
      )}
    </>
  );
}
