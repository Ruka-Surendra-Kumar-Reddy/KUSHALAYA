"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { useRouter } from "next/navigation";

import { Flash } from "@/components/Flash";
import {
  deleteBlogPost,
  getBlogPost,
  saveBlogPost,
  uploadBlogImage,
  type BlogAdminPost,
  type BlogFaq,
  type BlogInput,
  type BlogStatus,
} from "@/lib/blog/api";
import { Markdown } from "@/lib/blog/markdown";
import {
  EXCERPT_MAX,
  SEO_TITLE_MAX,
  blogDate,
  blogImageSrc,
  imagesMissingAlt,
  readingLabel,
  readingMinutes,
  slugify,
} from "@/lib/blog/text";
import "./blog.css";

const SITE = "www.kushalaya.com";

type Form = {
  title: string;
  slug: string;
  excerpt: string;
  body_md: string;
  cover_image_url: string;
  cover_image_alt: string;
  tags: string;
  author_name: string;
  seo_title: string;
  og_image_url: string;
  canonical_url: string;
  faq: BlogFaq[];
  publish_at: string; // datetime-local value
};

const EMPTY: Form = {
  title: "",
  slug: "",
  excerpt: "",
  body_md: "",
  cover_image_url: "",
  cover_image_alt: "",
  tags: "",
  author_name: "",
  seo_title: "",
  og_image_url: "",
  canonical_url: "",
  faq: [],
  publish_at: "",
};

/** ISO -> value for <input type="datetime-local"> in the browser's time. */
function localInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromPost(p: BlogAdminPost): Form {
  return {
    title: p.title,
    slug: p.slug,
    excerpt: p.excerpt,
    body_md: p.body_md,
    cover_image_url: p.cover_image_url,
    cover_image_alt: p.cover_image_alt,
    tags: (p.tags || []).join(", "),
    author_name: p.author_name,
    seo_title: p.seo_title,
    og_image_url: p.og_image_url,
    canonical_url: p.canonical_url,
    faq: p.faq || [],
    publish_at: localInput(p.publish_at),
  };
}

function Counter({ value, max }: { value: string; max: number }) {
  const n = value.length;
  const tone = n > max ? "over" : n > max * 0.9 ? "near" : n === 0 ? "empty" : "ok";
  return (
    <span className={`bl-count bl-count--${tone}`} aria-live="polite">
      {n}/{max}
    </span>
  );
}

/** Ask Next to refetch the public blog pages now rather than within 5 minutes. */
function refreshPublicSite() {
  fetch("/blog-cache", { method: "POST" }).catch(() => undefined);
}

type Tool = { label: string; title: string; run: (sel: string) => { text: string; block?: boolean } };

const TOOLS: Tool[] = [
  { label: "H2", title: "Section heading", run: (s) => ({ text: `## ${s || "Heading"}`, block: true }) },
  { label: "H3", title: "Sub-heading", run: (s) => ({ text: `### ${s || "Sub-heading"}`, block: true }) },
  { label: "B", title: "Bold", run: (s) => ({ text: `**${s || "bold text"}**` }) },
  { label: "I", title: "Italic", run: (s) => ({ text: `*${s || "italic text"}*` }) },
  { label: "Link", title: "Link", run: (s) => ({ text: `[${s || "link text"}](/kushcare-discovery)` }) },
  {
    label: "• List",
    title: "Bulleted list",
    run: (s) => ({ text: (s || "Item").split("\n").map((l) => `- ${l}`).join("\n"), block: true }),
  },
  {
    label: "1. List",
    title: "Numbered list",
    run: (s) => ({ text: (s || "Step").split("\n").map((l, i) => `${i + 1}. ${l}`).join("\n"), block: true }),
  },
  { label: "Quote", title: "Quote", run: (s) => ({ text: `> ${s || "Quote"}`, block: true }) },
];

export function BlogEditor({ postId }: { postId: number | null }) {
  const router = useRouter();
  const [id, setId] = useState<number | null>(postId);
  const [post, setPost] = useState<BlogAdminPost | null>(null);
  const [form, setForm] = useState<Form>(EMPTY);
  const [slugTouched, setSlugTouched] = useState(postId !== null);
  const [loading, setLoading] = useState(postId !== null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [savedForm, setSavedForm] = useState<Form>(EMPTY);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [bodyView, setBodyView] = useState<"write" | "preview">("write");
  const [pending, setPending] = useState<{ file: File; alt: string; target: "inline" | "cover" | "og" } | null>(null);
  const bodyRef = useRef<HTMLTextAreaElement>(null);
  const inlineFile = useRef<HTMLInputElement>(null);
  const coverFile = useRef<HTMLInputElement>(null);
  const ogFile = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (postId === null) return;
    getBlogPost(postId)
      .then((p) => {
        setPost(p);
        setForm(fromPost(p));
        setSavedForm(fromPost(p));
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [postId]);

  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm((f) => ({ ...f, [key]: value }));

  function setTitle(title: string) {
    setForm((f) => ({ ...f, title, slug: slugTouched ? f.slug : slugify(title) }));
  }

  const minutes = useMemo(() => readingMinutes(form.body_md), [form.body_md]);
  const missingAlt = imagesMissingAlt(form.body_md);
  const status: BlogStatus = post?.status || "draft";
  const isLive = Boolean(post?.live);

  const problems: string[] = [];
  if (!form.title.trim()) problems.push("Add a title.");
  if (!form.body_md.trim()) problems.push("Write the article.");
  if (missingAlt) problems.push(`${missingAlt} picture${missingAlt > 1 ? "s" : ""} in the article need alt text.`);
  if (form.cover_image_url && !form.cover_image_alt.trim()) problems.push("Describe the cover picture (alt text).");
  if (form.excerpt.length > EXCERPT_MAX) problems.push(`Shorten the summary to ${EXCERPT_MAX} characters.`);
  if (form.seo_title.length > SEO_TITLE_MAX) problems.push(`Shorten the search title to ${SEO_TITLE_MAX} characters.`);
  const tips: string[] = [];
  if (!form.excerpt.trim()) tips.push("Add a summary — Google shows it under the title.");
  if (!form.cover_image_url) tips.push("Add a cover picture — it shows on the blog page and when shared.");

  function payload(): BlogInput {
    return {
      title: form.title,
      slug: form.slug || slugify(form.title),
      excerpt: form.excerpt,
      body_md: form.body_md,
      cover_image_url: form.cover_image_url,
      cover_image_alt: form.cover_image_alt,
      tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean),
      author_name: form.author_name,
      seo_title: form.seo_title,
      og_image_url: form.og_image_url,
      canonical_url: form.canonical_url,
      faq: form.faq.filter((f) => f.q.trim() && f.a.trim()),
    };
  }

  async function save(action: "draft" | "publish" | "schedule" | "unpublish" | "save") {
    setError("");
    setMessage("");
    if (action !== "draft" && action !== "unpublish" && action !== "save" && problems.length) {
      setError(problems[0]);
      return;
    }
    const body = payload();
    if (action === "draft" || action === "unpublish") body.status = "draft";
    if (action === "publish") body.status = "published";
    if (action === "schedule") {
      if (!form.publish_at) return setError("Pick the date and time to publish.");
      const when = new Date(form.publish_at);
      if (when.getTime() <= Date.now()) return setError("Pick a time in the future, or use Publish now.");
      body.status = "scheduled";
      body.publish_at = when.toISOString();
    }
    setBusy(action);
    try {
      const saved = await saveBlogPost(id, body);
      setPost(saved);
      setForm(fromPost(saved));
      setSavedForm(fromPost(saved));
      setSlugTouched(true);
      if (!id) {
        setId(saved.id);
        router.replace(`/kushalaya/blog/${saved.id}`);
      }
      setMessage(
        action === "publish"
          ? "Published. It is on the website now."
          : action === "schedule"
            ? `Scheduled for ${new Date(saved.publish_at || "").toLocaleString("en-IN")}.`
            : action === "unpublish"
              ? "Unpublished. It is no longer on the website."
              : "Saved.",
      );
      if (action !== "draft" || status !== "draft") refreshPublicSite();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save the post");
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    if (!id || !window.confirm("Delete this post? This cannot be undone.")) return;
    setBusy("delete");
    try {
      await deleteBlogPost(id);
      refreshPublicSite();
      router.push("/kushalaya/blog");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete the post");
      setBusy(null);
    }
  }

  /** Put Markdown at the cursor (or around the selection). */
  function insert(make: Tool["run"]) {
    const ta = bodyRef.current;
    const value = form.body_md;
    const start = ta?.selectionStart ?? value.length;
    const end = ta?.selectionEnd ?? value.length;
    const { text, block } = make(value.slice(start, end));
    const before = value.slice(0, start);
    const after = value.slice(end);
    const pre = block && before && !before.endsWith("\n\n") ? (before.endsWith("\n") ? "\n" : "\n\n") : "";
    const post = block && after && !after.startsWith("\n") ? "\n\n" : "";
    const next = `${before}${pre}${text}${post}${after}`;
    set("body_md", next);
    requestAnimationFrame(() => {
      if (!ta) return;
      ta.focus();
      const pos = before.length + pre.length + text.length;
      ta.setSelectionRange(pos, pos);
    });
  }

  function pick(target: "inline" | "cover" | "og") {
    return (e: ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      e.target.value = "";
      if (!file) return;
      if (!/^image\/(jpeg|png|webp)$/.test(file.type)) return setError("Use a JPG, PNG or WebP picture.");
      if (file.size > 5 * 1024 * 1024) return setError("Pictures must be 5 MB or smaller.");
      setError("");
      setPending({ file, alt: target === "cover" ? form.cover_image_alt : "", target });
    };
  }

  async function uploadPending() {
    if (!pending) return;
    const alt = pending.alt.trim();
    if (pending.target !== "og" && !alt) return setError("Describe the picture first — screen readers and Google use it.");
    setBusy("upload");
    setError("");
    try {
      const img = await uploadBlogImage(pending.file, alt);
      if (pending.target === "inline") insert(() => ({ text: `![${alt.replace(/[[\]]/g, "")}](${img.url})`, block: true }));
      if (pending.target === "cover") setForm((f) => ({ ...f, cover_image_url: img.url, cover_image_alt: alt }));
      if (pending.target === "og") set("og_image_url", img.url);
      setPending(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not upload the picture");
    } finally {
      setBusy(null);
    }
  }

  const seoTitle = (form.seo_title || form.title || "Post title").trim();
  const serpTitle = seoTitle.length > 60 ? `${seoTitle.slice(0, 58)}…` : seoTitle;
  const serpDesc = form.excerpt || "Add a summary — Google usually shows it here, under the title.";
  const liveHref = `/marketing/blog/${post?.slug || form.slug}`;
  const dirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(savedForm), [form, savedForm]);
  const state =
    status === "draft"
      ? { text: "Draft", tone: "draft", note: "Only your team can see it." }
      : isLive
        ? { text: "Published", tone: "live", note: "Live on the website." }
        : {
            text: "Scheduled",
            tone: "soon",
            note: `Goes live ${post?.publish_at ? new Date(post.publish_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "soon"}.`,
          };
  const saveAction = status === "draft" ? "draft" : "save";

  // Ctrl/Cmd+S saves; warn before leaving with unsaved changes.
  const saveRef = useRef(() => {});
  saveRef.current = () => {
    if (!busy) void save(saveAction);
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        saveRef.current();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    if (!dirty) return;
    const onLeave = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onLeave);
    return () => window.removeEventListener("beforeunload", onLeave);
  }, [dirty]);
  const closePreview = useCallback(() => setPreviewOpen(false), []);

  if (loading) return <p className="muted">Loading…</p>;

  return (
    <div className="bl-editor">
      <div className="bl-bar">
        <Link className="bl-back" href="/kushalaya/blog">
          ← All posts
        </Link>
        <div className="bl-bar-title">
          <strong>{form.title.trim() || (id ? "Untitled post" : "New post")}</strong>
          <span className="bl-bar-sub">
            <span className={`bl-status bl-status--${state.tone}`}>{state.text}</span>
            <span className={dirty ? "bl-dirty" : "bl-clean"}>{dirty ? "Unsaved changes" : id ? "All changes saved" : "Not saved yet"}</span>
          </span>
        </div>
        <div className="bl-bar-actions">
          <button type="button" className="secondary" onClick={() => setPreviewOpen(true)}>
            Preview
          </button>
          <button type="button" className="secondary" disabled={!!busy} onClick={() => void save(saveAction)} title="Ctrl+S">
            {busy === "draft" || busy === "save" ? "Saving…" : status === "draft" ? "Save draft" : "Save changes"}
          </button>
          {status !== "published" || !isLive ? (
            <button type="button" disabled={!!busy} onClick={() => void save("publish")}>
              {busy === "publish" ? "Publishing…" : "Publish"}
            </button>
          ) : (
            <a className="bl-linkbtn" href={liveHref} target="_blank" rel="noopener noreferrer">
              View live ↗
            </a>
          )}
        </div>
      </div>

      <Flash error={error} message={message} onClear={() => { setError(""); setMessage(""); }} />

      <div className="bl-grid">
        <div className="bl-main">
          <section className="card bl-card bl-write">
            <label className="bl-field">
              <span className="sr-only">Title</span>
              <textarea
                className="bl-title-input"
                rows={2}
                value={form.title}
                onChange={(e) => setTitle(e.target.value.replace(/\n/g, " "))}
                placeholder="Post title"
                maxLength={200}
              />
            </label>
            <label className="bl-field">
              <span className="bl-label bl-label--sm">
                Summary <span className="bl-hint">shown on the blog page and in Google</span>
                <Counter value={form.excerpt} max={EXCERPT_MAX} />
              </span>
              <textarea
                rows={2}
                value={form.excerpt}
                maxLength={EXCERPT_MAX}
                onChange={(e) => set("excerpt", e.target.value.replace(/\n/g, " "))}
                placeholder="One or two sentences on what the reader will learn."
              />
            </label>

            <div className="bl-article">
              <div className="bl-toolbar" role="toolbar" aria-label="Formatting">
                {TOOLS.map((t) => (
                  <button key={t.label} type="button" title={t.title} aria-label={t.title} onClick={() => insert(t.run)}>
                    {t.label}
                  </button>
                ))}
                <button type="button" title="Insert picture" onClick={() => inlineFile.current?.click()}>
                  + Picture
                </button>
                <input ref={inlineFile} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={pick("inline")} />
                <span className="bl-toolbar-info">{readingLabel(minutes)}</span>
              </div>
              <div className="bl-body-tabs" role="group" aria-label="Article view">
                <button type="button" aria-pressed={bodyView === "write"} onClick={() => setBodyView("write")}>
                  Write
                </button>
                <button type="button" aria-pressed={bodyView === "preview"} onClick={() => setBodyView("preview")}>
                  Preview
                </button>
              </div>
              {bodyView === "preview" ? (
                <div className="bl-body-preview">
                  {form.body_md.trim() ? <Markdown source={form.body_md} className="bl-prose" /> : <p className="muted">Nothing written yet.</p>}
                </div>
              ) : (
                <textarea
                  ref={bodyRef}
                  className="bl-body"
                  value={form.body_md}
                  onChange={(e) => set("body_md", e.target.value)}
                  placeholder={"Start writing your article here.\n\nUse the buttons above for headings, lists, links and pictures. Click Preview to see it as readers will."}
                  aria-label="Article"
                />
              )}
            </div>
          </section>

          <section className="card bl-card">
            <div className="bl-card-head">
              <h2>Questions &amp; answers</h2>
              <span className="bl-hint">Optional. Shown at the end of the post and in Google results.</span>
            </div>
            {form.faq.map((f, i) => (
              <div className="bl-faq" key={i}>
                <span className="bl-faq-num" aria-hidden="true">
                  {i + 1}
                </span>
                <div className="bl-faq-fields">
                  <input
                    value={f.q}
                    placeholder="Question"
                    aria-label={`Question ${i + 1}`}
                    onChange={(e) => set("faq", form.faq.map((x, j) => (j === i ? { ...x, q: e.target.value } : x)))}
                  />
                  <textarea
                    rows={2}
                    value={f.a}
                    placeholder="Answer"
                    aria-label={`Answer ${i + 1}`}
                    ref={autoGrow}
                    onInput={(e) => autoGrow(e.currentTarget)}
                    onChange={(e) => set("faq", form.faq.map((x, j) => (j === i ? { ...x, a: e.target.value } : x)))}
                  />
                </div>
                <button
                  type="button"
                  className="bl-icon-btn"
                  aria-label={`Remove question ${i + 1}`}
                  title="Remove"
                  onClick={() => set("faq", form.faq.filter((_, j) => j !== i))}
                >
                  ✕
                </button>
              </div>
            ))}
            <button type="button" className="secondary bl-add" onClick={() => set("faq", [...form.faq, { q: "", a: "" }])}>
              + Add a question
            </button>
          </section>
        </div>

        <aside className="bl-side">
          <section className="card bl-card">
            <div className="bl-card-head">
              <h2>Publishing</h2>
              <span className={`bl-status bl-status--${state.tone}`}>{state.text}</span>
            </div>
            <p className="bl-note">{state.note}</p>
            {problems.length || tips.length ? (
              <ul className="bl-checks" aria-label="Before publishing">
                {problems.map((p) => (
                  <li key={p} className="is-bad">
                    {p}
                  </li>
                ))}
                {tips.map((p) => (
                  <li key={p} className="is-tip">
                    {p}
                  </li>
                ))}
              </ul>
            ) : (
              status === "published" ? (
                <p className="bl-ready bl-live">● Live on the website</p>
              ) : (
                <p className="bl-ready">✓ Ready to publish</p>
              )
            )}
            {status === "draft" ? (
              <details className="bl-more">
                <summary>Schedule for later</summary>
                <div className="bl-schedule">
                  <input type="datetime-local" aria-label="Publish on" value={form.publish_at} onChange={(e) => set("publish_at", e.target.value)} />
                  <button type="button" className="secondary" disabled={!!busy} onClick={() => void save("schedule")}>
                    {busy === "schedule" ? "Scheduling…" : "Schedule"}
                  </button>
                </div>
                <span className="bl-hint">India time (IST).</span>
              </details>
            ) : (
              <button type="button" className="secondary" disabled={!!busy} onClick={() => void save("unpublish")}>
                {busy === "unpublish" ? "Unpublishing…" : "Unpublish (back to draft)"}
              </button>
            )}
          </section>

          <section className="card bl-card">
            <div className="bl-card-head">
              <h2>Cover picture</h2>
            </div>
            {form.cover_image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img className="bl-cover" src={blogImageSrc(form.cover_image_url)} alt={form.cover_image_alt || ""} />
            ) : (
              <button type="button" className="bl-cover bl-cover--empty" onClick={() => coverFile.current?.click()}>
                + Add a cover picture
                <span className="bl-hint">1200 × 675 (16:9), JPG or WebP, under 5 MB</span>
              </button>
            )}
            {form.cover_image_url ? (
              <>
                <label className="bl-field">
                  <span className="bl-label bl-label--sm">
                    Describe the picture <span className="bl-req">required</span>
                  </span>
                  <input
                    value={form.cover_image_alt}
                    onChange={(e) => set("cover_image_alt", e.target.value)}
                    placeholder="What the picture shows, in a sentence"
                    maxLength={200}
                  />
                </label>
                <div className="bl-row">
                  <button type="button" className="secondary" onClick={() => coverFile.current?.click()}>
                    Replace
                  </button>
                  <button type="button" className="secondary" onClick={() => set("cover_image_url", "")}>
                    Remove
                  </button>
                </div>
              </>
            ) : null}
            <input ref={coverFile} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={pick("cover")} />
          </section>

          <section className="card bl-card">
            <div className="bl-card-head">
              <h2>Details</h2>
            </div>
            <label className="bl-field">
              <span className="bl-label bl-label--sm">Web address</span>
              <div className="bl-url">
                <span>/blog/</span>
                <input
                  value={form.slug}
                  onChange={(e) => {
                    setSlugTouched(true);
                    set("slug", e.target.value.toLowerCase().replace(/[^a-z0-9-]+/g, "-"));
                  }}
                  onBlur={() => set("slug", slugify(form.slug || form.title))}
                  placeholder="made-from-the-title"
                />
              </div>
              <span className="bl-url-full">
                {SITE}/blog/{form.slug || "…"}
              </span>
            </label>
            <label className="bl-field">
              <span className="bl-label bl-label--sm">
                Tags <span className="bl-hint">separate with commas</span>
              </span>
              <input value={form.tags} onChange={(e) => set("tags", e.target.value)} placeholder="elder care, hyderabad, home safety" />
            </label>
            <label className="bl-field">
              <span className="bl-label bl-label--sm">Author</span>
              <input value={form.author_name} onChange={(e) => set("author_name", e.target.value)} placeholder="KushAlaya care team" maxLength={120} />
            </label>
          </section>

          <section className="card bl-card">
            <div className="bl-card-head">
              <h2>Google preview</h2>
            </div>
            <div className="bl-serp" aria-label="Google search preview">
              <div className="bl-serp-site">
                <span className="bl-serp-fav" aria-hidden="true">
                  K
                </span>
                <span>
                  <strong>KushAlaya</strong>
                  <small>
                    https://{SITE} › blog › {form.slug || "…"}
                  </small>
                </span>
              </div>
              <div className="bl-serp-title">{serpTitle}</div>
              <div className="bl-serp-desc">
                {post?.published_at ? <span className="bl-serp-date">{blogDate(post.published_at)} — </span> : null}
                {serpDesc.length > 160 ? `${serpDesc.slice(0, 157)}…` : serpDesc}
              </div>
            </div>
            <details className="bl-more">
              <summary>Advanced search &amp; sharing</summary>
              <label className="bl-field">
                <span className="bl-label bl-label--sm">
                  Search title <span className="bl-hint">blank = post title</span>
                  <Counter value={form.seo_title} max={SEO_TITLE_MAX} />
                </span>
                <input value={form.seo_title} onChange={(e) => set("seo_title", e.target.value)} placeholder={form.title} maxLength={SEO_TITLE_MAX} />
              </label>
              <label className="bl-field">
                <span className="bl-label bl-label--sm">
                  Share picture <span className="bl-hint">blank = cover</span>
                </span>
                <div className="bl-row">
                  <input value={form.og_image_url} onChange={(e) => set("og_image_url", e.target.value)} placeholder="Uses the cover picture" />
                  <button type="button" className="secondary" onClick={() => ogFile.current?.click()}>
                    Upload
                  </button>
                </div>
                <input ref={ogFile} type="file" accept="image/jpeg,image/png" hidden onChange={pick("og")} />
              </label>
              <label className="bl-field">
                <span className="bl-label bl-label--sm">
                  Canonical URL <span className="bl-hint">only if first published elsewhere</span>
                </span>
                <input value={form.canonical_url} onChange={(e) => set("canonical_url", e.target.value)} placeholder={`https://${SITE}/blog/${form.slug || "…"}`} />
              </label>
            </details>
          </section>

          {id ? (
            <button type="button" className="bl-delete" disabled={!!busy} onClick={() => void remove()}>
              Delete this post
            </button>
          ) : null}
        </aside>
      </div>

      {previewOpen ? <BlogPreview form={form} minutes={minutes} date={post?.published_at || null} onClose={closePreview} /> : null}

      {pending ? (
        <div className="bl-modal" role="dialog" aria-modal="true" aria-labelledby="bl-modal-title">
          <div className="bl-modal-card card">
            <h2 id="bl-modal-title">{pending.target === "inline" ? "Insert picture" : pending.target === "cover" ? "Cover picture" : "Share picture"}</h2>
            <p className="muted">{pending.file.name}</p>
            {pending.target !== "og" ? (
              <label className="bl-field">
                <span className="bl-label bl-label--sm">
                  Describe the picture <span className="bl-req">required</span>
                </span>
                <input
                  autoFocus
                  value={pending.alt}
                  onChange={(e) => setPending({ ...pending, alt: e.target.value })}
                  placeholder="e.g. A grab bar fitted beside the toilet"
                  maxLength={200}
                />
              </label>
            ) : null}
            <div className="bl-row bl-row--end">
              <button type="button" className="secondary" onClick={() => setPending(null)}>
                Cancel
              </button>
              <button type="button" disabled={busy === "upload"} onClick={() => void uploadPending()}>
                {busy === "upload" ? "Uploading…" : pending.target === "inline" ? "Insert" : "Use picture"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

/** Full-screen preview: the post as readers will see it, at laptop or phone width. */
function BlogPreview({ form, minutes, date, onClose }: { form: Form; minutes: number; date: string | null; onClose: () => void }) {
  const [device, setDevice] = useState<"laptop" | "phone">("laptop");
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
    };
  }, [onClose]);
  const tags = form.tags.split(",").map((t) => t.trim()).filter(Boolean);
  const faq = form.faq.filter((f) => f.q.trim() && f.a.trim());
  return (
    <div className="bl-pv" role="dialog" aria-modal="true" aria-label="Preview">
      <div className="bl-pv-bar">
        <div className="bl-pv-name">
          <strong>Preview</strong>
          <span className="bl-hint">How readers will see it</span>
        </div>
        <div className="bl-seg" role="group" aria-label="Screen size">
          <button type="button" aria-pressed={device === "laptop"} className={device === "laptop" ? "is-on" : ""} onClick={() => setDevice("laptop")}>
            Laptop
          </button>
          <button type="button" aria-pressed={device === "phone"} className={device === "phone" ? "is-on" : ""} onClick={() => setDevice("phone")}>
            Phone
          </button>
        </div>
        <button type="button" onClick={onClose}>
          Back to editing
        </button>
      </div>
      <div className="bl-pv-stage">
        <article className={`bl-pv-page bl-pv-page--${device}`}>
          {tags.length ? (
            <ul className="bl-pv-tags">
              {tags.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          ) : null}
          <h1>{form.title.trim() || "Untitled post"}</h1>
          {form.excerpt ? <p className="bl-pv-lede">{form.excerpt}</p> : null}
          <p className="bl-pv-meta">
            By {form.author_name || "KushAlaya care team"} · {date ? blogDate(date) : "Not published yet"} · {readingLabel(minutes)}
          </p>
          {form.cover_image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img className="bl-pv-cover" src={blogImageSrc(form.cover_image_url)} alt={form.cover_image_alt || ""} />
          ) : null}
          {form.body_md.trim() ? <Markdown source={form.body_md} className="bl-prose bl-pv-prose" /> : <p className="muted">Nothing written yet.</p>}
          {faq.length ? (
            <section className="bl-pv-faq">
              <h2>Questions families ask</h2>
              {faq.map((f) => (
                <details key={f.q} open>
                  <summary>{f.q}</summary>
                  <Markdown source={f.a} className="bl-prose" />
                </details>
              ))}
            </section>
          ) : null}
        </article>
      </div>
    </div>
  );
}

/** Grow a textarea to fit its text (fallback where CSS field-sizing is not supported). */
function autoGrow(el: HTMLTextAreaElement | null) {
  if (!el) return;
  el.style.height = "auto";
  el.style.height = `${el.scrollHeight + 2}px`;
}
