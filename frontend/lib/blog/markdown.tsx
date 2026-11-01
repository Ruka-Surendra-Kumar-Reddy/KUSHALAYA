import { Fragment, type ReactNode } from "react";

import { blogImageSrc, safeHref, slugify } from "./text";

/**
 * A small Markdown renderer for blog posts that builds React elements — never
 * HTML strings — so nothing in a post can inject markup or script. Raw HTML in
 * the source shows as plain text (the API strips it on save anyway); link and
 * image targets go through safeHref / blogImageSrc.
 *
 * Supports: ## / ### / #### headings (a single # becomes h2: the page title is
 * the only h1), paragraphs, - and 1. lists, > quotes, --- rules, ``` code,
 * **bold**, *italic*, `code`, [links](url) and ![alt](url) images.
 */

type Block =
  | { kind: "h"; level: 2 | 3 | 4; text: string }
  | { kind: "p"; text: string }
  | { kind: "ul" | "ol"; items: string[] }
  | { kind: "quote"; text: string }
  | { kind: "hr" }
  | { kind: "code"; text: string }
  | { kind: "img"; alt: string; src: string };

const IMG_LINE = /^!\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+"[^"]*")?\s*\)$/;
const UL = /^\s*[-*+]\s+(.*)$/;
const OL = /^\s*\d+[.)]\s+(.*)$/;
const HEADING = /^(#{1,6})\s+(.*?)\s*#*$/;
const HR = /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/;

function isBlockStart(line: string): boolean {
  return HEADING.test(line) || HR.test(line) || UL.test(line) || OL.test(line) || line.startsWith(">") || line.startsWith("```") || IMG_LINE.test(line.trim());
}

export function parseBlocks(md: string): Block[] {
  const lines = (md || "").replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    if (line.startsWith("```")) {
      const body: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) body.push(lines[i++]);
      i++;
      blocks.push({ kind: "code", text: body.join("\n") });
      continue;
    }
    const h = HEADING.exec(line);
    if (h) {
      const level = Math.min(4, Math.max(2, h[1].length)) as 2 | 3 | 4;
      blocks.push({ kind: "h", level, text: h[2] });
      i++;
      continue;
    }
    if (HR.test(line)) {
      blocks.push({ kind: "hr" });
      i++;
      continue;
    }
    const img = IMG_LINE.exec(line.trim());
    if (img) {
      blocks.push({ kind: "img", alt: img[1], src: img[2] });
      i++;
      continue;
    }
    if (line.startsWith(">")) {
      const body: string[] = [];
      while (i < lines.length && lines[i].startsWith(">")) body.push(lines[i++].replace(/^>\s?/, ""));
      blocks.push({ kind: "quote", text: body.join(" ") });
      continue;
    }
    const listRe = UL.test(line) ? UL : OL.test(line) ? OL : null;
    if (listRe) {
      const items: string[] = [];
      while (i < lines.length) {
        const m = listRe.exec(lines[i]);
        if (m) {
          items.push(m[1]);
          i++;
        } else if (lines[i].trim() && /^\s{2,}/.test(lines[i]) && items.length) {
          items[items.length - 1] += ` ${lines[i].trim()}`; // wrapped item
          i++;
        } else break;
      }
      blocks.push({ kind: listRe === UL ? "ul" : "ol", items });
      continue;
    }
    const body: string[] = [];
    while (i < lines.length && lines[i].trim() && !isBlockStart(lines[i])) body.push(lines[i++].trim());
    blocks.push({ kind: "p", text: body.join(" ") });
  }
  return blocks;
}

const INLINE = /(`[^`]+`)|(!\[[^\]]*\]\([^)\s]+\))|(\[[^\]]+\]\([^)\s]+\))|(\*\*[^*]+\*\*)|(\*[^*\s][^*]*\*|_[^_\s][^_]*_)/;

function inline(text: string, key = "i"): ReactNode[] {
  const out: ReactNode[] = [];
  let rest = text;
  let n = 0;
  while (rest) {
    const m = INLINE.exec(rest);
    if (!m) {
      out.push(rest);
      break;
    }
    if (m.index > 0) out.push(rest.slice(0, m.index));
    const tok = m[0];
    const k = `${key}-${n++}`;
    if (m[1]) out.push(<code key={k}>{tok.slice(1, -1)}</code>);
    else if (m[2]) {
      const im = /^!\[([^\]]*)\]\(([^)\s]+)\)$/.exec(tok)!;
      const src = blogImageSrc(im[2]);
      // eslint-disable-next-line @next/next/no-img-element
      if (src) out.push(<img key={k} src={src} alt={im[1]} loading="lazy" decoding="async" />);
    } else if (m[3]) {
      const lm = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(tok)!;
      const href = safeHref(lm[2]);
      const external = /^https?:\/\//i.test(href);
      out.push(
        <a key={k} href={href} {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}>
          {inline(lm[1], k)}
        </a>,
      );
    } else if (m[4]) out.push(<strong key={k}>{inline(tok.slice(2, -2), k)}</strong>);
    else out.push(<em key={k}>{inline(tok.slice(1, -1), k)}</em>);
    rest = rest.slice(m.index + tok.length);
  }
  return out;
}

/** Plain text of a heading (for its id and a table of contents). */
function headingText(text: string): string {
  return text.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/[*_`]/g, "");
}

export function markdownHeadings(md: string): { id: string; text: string; level: number }[] {
  return parseBlocks(md)
    .filter((b): b is Extract<Block, { kind: "h" }> => b.kind === "h")
    .map((b) => ({ id: slugify(headingText(b.text)), text: headingText(b.text), level: b.level }));
}

export function Markdown({ source, className }: { source: string; className?: string }) {
  const blocks = parseBlocks(source);
  return (
    <div className={className}>
      {blocks.map((b, idx) => {
        const k = `b${idx}`;
        switch (b.kind) {
          case "h": {
            const id = slugify(headingText(b.text));
            const Tag = `h${b.level}` as "h2" | "h3" | "h4";
            return (
              <Tag key={k} id={id}>
                {inline(b.text, k)}
              </Tag>
            );
          }
          case "p":
            return <p key={k}>{inline(b.text, k)}</p>;
          case "ul":
            return (
              <ul key={k}>
                {b.items.map((it, j) => (
                  <li key={j}>{inline(it, `${k}-${j}`)}</li>
                ))}
              </ul>
            );
          case "ol":
            return (
              <ol key={k}>
                {b.items.map((it, j) => (
                  <li key={j}>{inline(it, `${k}-${j}`)}</li>
                ))}
              </ol>
            );
          case "quote":
            return <blockquote key={k}>{inline(b.text, k)}</blockquote>;
          case "hr":
            return <hr key={k} />;
          case "code":
            return (
              <pre key={k}>
                <code>{b.text}</code>
              </pre>
            );
          case "img": {
            const src = blogImageSrc(b.src);
            if (!src) return <Fragment key={k} />;
            return (
              <figure key={k}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={src} alt={b.alt} width={1200} height={800} loading="lazy" decoding="async" />
              </figure>
            );
          }
        }
      })}
    </div>
  );
}
