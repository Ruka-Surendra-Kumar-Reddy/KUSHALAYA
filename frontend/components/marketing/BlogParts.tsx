"use client";

import { useState } from "react";

import { PARENT_CARE_CHECK_HREF } from "@/lib/marketing/family-contacts";
import { CALLBACK_PROMISE, useSiteConfig, whatsAppHref } from "@/lib/marketing/site-config";
import { MkLink as Link } from "./MkLink";
import { ICONS } from "./ui";

/** Desktop-only sticky booking card in the article's right column. */
export function BlogSideCard({ title }: { title: string }) {
  const site = useSiteConfig();
  return (
    <aside className="mb-side" aria-label="Talk to us">
      <div className="mb-side-card">
        <p className="mb-side-title">Worried about a parent back home?</p>
        <p>{CALLBACK_PROMISE} — free, with no obligation.</p>
        <Link className="mk-btn mk-btn-primary" href={PARENT_CARE_CHECK_HREF}>
          Start KushCare Discovery {ICONS.arrow}
        </Link>
        <a
          className="mk-btn mk-btn-green"
          href={whatsAppHref(site, `Hi, I read "${title}" and would like to talk about my parents.`)}
          target="_blank"
          rel="noopener noreferrer"
        >
          {ICONS.whatsapp} WhatsApp us
        </a>
      </div>
    </aside>
  );
}

/** "Start KushCare Discovery" + WhatsApp box at the end of an article. */
export function BlogCta({ title }: { title: string }) {
  const site = useSiteConfig();
  return (
    <aside className="mb-cta" aria-labelledby="mb-cta-title">
      <h2 id="mb-cta-title">Worried about a parent back home?</h2>
      <p>
        Tell us about them in a few minutes, from anywhere. {CALLBACK_PROMISE} to talk it through — free, with no
        obligation.
      </p>
      <div className="mb-cta-actions">
        <Link className="mk-btn mk-btn-primary mk-btn-lg" href={PARENT_CARE_CHECK_HREF}>
          Start KushCare Discovery {ICONS.arrow}
        </Link>
        <a
          className="mk-btn mk-btn-green mk-btn-lg"
          href={whatsAppHref(site, `Hi, I read "${title}" and would like to talk about my parents.`)}
          target="_blank"
          rel="noopener noreferrer"
        >
          {ICONS.whatsapp} WhatsApp us
        </a>
      </div>
    </aside>
  );
}

/** Share links (no third-party scripts) plus copy-link. */
export function BlogShare({ url, title }: { url: string; title: string }) {
  const [copied, setCopied] = useState(false);
  const u = encodeURIComponent(url);
  const t = encodeURIComponent(title);
  const links = [
    { label: "WhatsApp", href: `https://wa.me/?text=${t}%20${u}` },
    { label: "Facebook", href: `https://www.facebook.com/sharer/sharer.php?u=${u}` },
    { label: "LinkedIn", href: `https://www.linkedin.com/sharing/share-offsite/?url=${u}` },
    { label: "X", href: `https://twitter.com/intent/tweet?url=${u}&text=${t}` },
    { label: "Email", href: `mailto:?subject=${t}&body=${u}` },
  ];
  return (
    <div className="mb-share" role="group" aria-label="Share this article">
      <span className="mb-share-label">Share</span>
      {links.map((l) => (
        <a
          key={l.label}
          className="mb-share-btn"
          href={l.href}
          target={l.label === "Email" ? undefined : "_blank"}
          rel="noopener noreferrer"
          aria-label={`Share on ${l.label}`}
        >
          {l.label}
        </a>
      ))}
      <button
        type="button"
        className="mb-share-btn"
        onClick={() => {
          navigator.clipboard
            ?.writeText(url)
            .then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 2000);
            })
            .catch(() => undefined);
        }}
      >
        {copied ? "Link copied" : "Copy link"}
      </button>
    </div>
  );
}
