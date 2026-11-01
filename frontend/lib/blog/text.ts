/**
 * Blog text helpers shared by the ops editor and the public pages. They mirror
 * backend/app/livewell/blog.py (slugify, reading_minutes) so the editor shows
 * the same address and reading time the server will store.
 */

export const EXCERPT_MAX = 160;
export const SEO_TITLE_MAX = 70;
export const SLUG_MAX = 100;
const WORDS_PER_MINUTE = 200;

/** "Caring for Parents — Hyderabad!" -> "caring-for-parents-hyderabad" */
export function slugify(text: string): string {
  const ascii = (text || "").normalize("NFKD").replace(/[^\x00-\x7f]/g, "");
  const slug = ascii
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, SLUG_MAX)
    .replace(/-+$/g, "");
  return slug || "post";
}

/** Words a reader reads: image syntax dropped, link text kept, Markdown marks ignored. */
export function plainWords(md: string): string[] {
  const text = (md || "")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/[#>*_`~\-|]+/g, " ");
  return text.split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w));
}

export function readingMinutes(md: string): number {
  return Math.max(1, Math.ceil(plainWords(md).length / WORDS_PER_MINUTE));
}

/** "6 min read" */
export function readingLabel(minutes: number): string {
  return `${Math.max(1, minutes || 1)} min read`;
}

/** Images in the Markdown that have no alt text — publishing is blocked until they do. */
export function imagesMissingAlt(md: string): number {
  return (md.match(/!\[\s*\]\(/g) || []).length;
}

/** Long date in India time, e.g. "11 October 2026". */
export function blogDate(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric", timeZone: "Asia/Kolkata" });
}

/** Link targets the renderer allows: http(s), mailto, tel, site paths and #anchors. Anything else becomes "#". */
export function safeHref(url: string): string {
  const u = (url || "").trim();
  if (!u) return "#";
  if (u.startsWith("#")) return u;
  if (u.startsWith("/") && !u.startsWith("//")) return u;
  if (/^(https?:\/\/|mailto:|tel:)/i.test(u)) return u;
  return "#";
}

/** Image sources: http(s) or a site path only. */
export function safeImageSrc(url: string): string {
  const u = (url || "").trim();
  if (u.startsWith("/") && !u.startsWith("//")) return u;
  return /^https?:\/\//i.test(u) ? u : "";
}

/** API base for blog image URLs ("/api/v1/public/blog/images/…"); site paths stay relative. */
export function blogApiBase(): string {
  return (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
}

export function blogImageSrc(url?: string | null): string {
  const u = safeImageSrc(url || "");
  if (!u) return "";
  return u.startsWith("/api/") ? `${blogApiBase()}${u}` : u;
}

/** Brand words keep their own capitals in tag labels. */
const TAG_BRANDS: Record<string, string> = { kushlife: "KushLife", kushalaya: "KushAlaya" };
const TAG_ACRONYMS = new Set(["ai", "nri", "sos", "uk", "us", "usa", "uae", "diy", "faq", "bls", "cpr", "gps", "iot"]);
const TAG_SMALL_WORDS = new Set(["a", "an", "and", "at", "for", "in", "of", "on", "or", "the", "to"]);

/** Display form of a stored (lowercase) tag: "ai room check" -> "AI Room Check". */
export function tagLabel(tag: string): string {
  return tag
    .trim()
    .split(/\s+/)
    .map((w, i) => {
      const lw = w.toLowerCase();
      if (TAG_BRANDS[lw]) return TAG_BRANDS[lw];
      if (TAG_ACRONYMS.has(lw)) return lw.toUpperCase();
      if (i > 0 && TAG_SMALL_WORDS.has(lw)) return lw;
      return w === lw ? lw.charAt(0).toUpperCase() + lw.slice(1) : w;
    })
    .join(" ");
}
