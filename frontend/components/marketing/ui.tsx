"use client";

import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

import { getApiUrl } from "@/lib/api";

/** Wraps a block that fades and rises into view the first time it scrolls in. */
export function Reveal({
  children,
  delay = 0,
  className = "",
  as: Tag = "div",
  id,
  ...rest
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "section" | "li" | "article" | "figure";
  id?: string;
  [key: string]: unknown;
}) {
  const ref = useRef<HTMLElement | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    // Tells the boot script in app/marketing/layout.tsx that React is running.
    document.documentElement.classList.add("mk-hydrated");
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setInView(true);
          io.disconnect();
        }
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.12 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const style = { "--mk-delay": `${delay}ms` } as CSSProperties;
  const Comp = Tag as unknown as "div";
  return (
    <Comp
      ref={ref as never}
      id={id}
      className={`mk-reveal${inView ? " is-in" : ""}${className ? ` ${className}` : ""}`}
      style={style}
      {...rest}
    >
      {children}
    </Comp>
  );
}

/** Counts from 0 to `value` once visible. Renders the final value immediately for SSR. */
export function Counter({ value, suffix = "" }: { value: number; suffix?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [shown, setShown] = useState(value);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) {
      setShown(value);
      return;
    }
    const io = new IntersectionObserver((entries) => {
      if (!entries.some((e) => e.isIntersecting) || started.current) return;
      started.current = true;
      io.disconnect();
      const t0 = performance.now();
      const dur = 1400;
      const tick = (t: number) => {
        const k = Math.min(1, (t - t0) / dur);
        const eased = 1 - Math.pow(1 - k, 3);
        setShown(Math.round(value * eased));
        if (k < 1) requestAnimationFrame(tick);
      };
      setShown(0);
      requestAnimationFrame(tick);
    });
    io.observe(el);
    return () => io.disconnect();
  }, [value]);

  // If the live value changes after the count-up ran, show it directly.
  useEffect(() => {
    if (started.current) setShown(value);
  }, [value]);

  return (
    <span ref={ref}>
      {shown.toLocaleString("en-IN")}
      {suffix}
    </span>
  );
}

/* Outline icons used across the site. */
const svg = (body: ReactNode) => (
  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    {body}
  </svg>
);

export const ICONS = {
  home: svg(<path d="M3 10.5 12 3l9 7.5V21a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />),
  bath: svg(
    <>
      <path d="M4 13h16v2a4 4 0 0 1-4 4H8a4 4 0 0 1-4-4z" />
      <path d="M6 13V6a2 2 0 0 1 4 0M7 19l-1 2M17 19l1 2" />
    </>,
  ),
  walk: svg(
    <>
      <circle cx="13" cy="4" r="1.6" />
      <path d="m9 21 2-6 3 2v4M8 12l3-4 3 1 2 3h3M11 8l-1 5-3 2" />
    </>,
  ),
  pill: svg(
    <>
      <rect x="3" y="8" width="18" height="8" rx="4" transform="rotate(-45 12 12)" />
      <path d="m8.5 8.5 7 7" />
    </>,
  ),
  bell: svg(
    <>
      <path d="M6 8a6 6 0 0 1 12 0v5l2 3H4l2-3z" />
      <path d="M10 20a2 2 0 0 0 4 0" />
    </>,
  ),
  chat: svg(<path d="M21 12a8 8 0 0 1-8 8H7l-4 3V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8z" />),
  heart: svg(<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" />),
  shield: svg(
    <>
      <path d="M12 3 4 6v6c0 5 3.4 8.4 8 9 4.6-.6 8-4 8-9V6z" />
      <path d="m9 12 2 2 4-4" />
    </>,
  ),
  check: svg(<path d="m5 12 4.5 4.5L19 7" />),
  arrow: svg(<path d="M5 12h14M13 6l6 6-6 6" />),
  phone: svg(
    <path d="M5 4h3l2 5-2.5 1.5a11 11 0 0 0 5 5L14 13l5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z" />,
  ),
  mail: svg(
    <>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </>,
  ),
  whatsapp: svg(
    <>
      <path d="M20 11.5a8 8 0 0 1-11.7 7L4 20l1.5-4.2A8 8 0 1 1 20 11.5z" />
      <path d="M9.5 9.5c.3 2 1.8 3.5 3.8 3.8l1-1 1.7.9-.4 1.3c-3.2.3-6.5-3-6.2-6.2l1.3-.4.9 1.7z" />
    </>,
  ),
  calendar: svg(
    <>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M8 3v4M16 3v4M3 11h18" />
    </>,
  ),
  clipboard: svg(
    <>
      <rect x="5" y="4" width="14" height="17" rx="2" />
      <path d="M9 4V3h6v1M9 11l2 2 4-4M9 16h6" />
    </>,
  ),
  tool: svg(
    <>
      <path d="M14.7 6.3a4 4 0 0 0 4.9 4.9l2.4 2.4-2.8 2.8-2.4-2.4a4 4 0 0 0-4.9-4.9L9.5 6.7 6.7 9.5 4 6.8 6.8 4l2.7 2.7z" />
      <path d="m3 21 6-6" />
    </>,
  ),
  users: svg(
    <>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3 20a6 6 0 0 1 12 0" />
      <circle cx="17" cy="9" r="2.4" />
      <path d="M15 20a5 5 0 0 1 6-4.6" />
    </>,
  ),
  globe: svg(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" />
    </>,
  ),
  clock: svg(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>,
  ),
  star: svg(<path d="M12 3l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.4 6.8 19.1l1-5.8L3.5 9.2l5.9-.9z" />),
  plus: svg(<path d="M12 5v14M5 12h14" />),
  menu: svg(<path d="M4 7h16M4 12h16M4 17h16" />),
  close: svg(<path d="M6 6l12 12M18 6L6 18" />),
  pin: svg(
    <>
      <path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z" />
      <circle cx="12" cy="9.5" r="2.5" />
    </>,
  ),
  doc: svg(
    <>
      <path d="M5 3h9l5 5v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
      <path d="M14 3v5h5M8 13h8M8 17h5" />
    </>,
  ),
  headset: svg(
    <>
      <path d="M4 14v-2a8 8 0 0 1 16 0v2" />
      <rect x="3" y="13" width="4" height="6" rx="1.5" />
      <rect x="17" y="13" width="4" height="6" rx="1.5" />
      <path d="M19 19a3 3 0 0 1-3 3h-3" />
    </>,
  ),
} as const;

export type IconName = keyof typeof ICONS;

/* ------------------------------------------------------------------------ */

/** Responsive photo: 700px copy for phones, 1400px for everything else. */
export function Photo({
  src,
  alt,
  wide = false,
  priority = false,
  className = "",
}: {
  src: string;
  alt: string;
  wide?: boolean;
  priority?: boolean;
  className?: string;
}) {
  const small = src.replace(/\.webp$/, "-700.webp");
  const h = wide ? 788 : 933;
  return (
    <figure className={`mk-photo${wide ? " is-wide" : ""}${className ? ` ${className}` : ""}`}>
      {/* eslint-disable-next-line @next/next/no-img-element -- static marketing asset */}
      <img
        src={src}
        srcSet={`${small} 700w, ${src} 1400w`}
        sizes="(min-width: 900px) 50vw, 100vw"
        alt={alt}
        width={1400}
        height={h}
        loading={priority ? "eager" : "lazy"}
        fetchPriority={priority ? "high" : undefined}
        decoding="async"
      />
    </figure>
  );
}

/** Two-column page hero used by every inner page. */
export function PageHero({
  eyebrow,
  title,
  accent,
  lede,
  image,
  imageAlt,
  children,
}: {
  eyebrow: string;
  title: string;
  accent?: string;
  lede: ReactNode;
  image?: string;
  imageAlt?: string;
  children?: ReactNode;
}) {
  return (
    <section className="mk-hero" id="top">
      <div className="mk-wrap mk-hero-grid">
        <Reveal>
          <p className="mk-eyebrow">{eyebrow}</p>
          <h1>
            {title}
            {accent ? <span className="mk-accent">{accent}</span> : null}
          </h1>
          <p className="mk-lede">{lede}</p>
          {children ? <div className="mk-actions">{children}</div> : null}
        </Reveal>
        {image ? (
          <Reveal delay={120} className="mk-hero-stage">
            <Photo src={image} alt={imageAlt ?? ""} priority />
          </Reveal>
        ) : null}
      </div>
    </section>
  );
}

export function SectionHead({
  eyebrow,
  title,
  sub,
  center = false,
  id,
}: {
  eyebrow: string;
  title: string;
  sub?: ReactNode;
  center?: boolean;
  id?: string;
}) {
  return (
    <Reveal className={`mk-section-head${center ? " is-center" : ""}`}>
      <p className="mk-eyebrow">{eyebrow}</p>
      <h2 id={id}>{title}</h2>
      {sub ? <p className="mk-sub">{sub}</p> : null}
    </Reveal>
  );
}

export type LiveStats = { families: number; visits: number; assessments: number };

/**
 * Aggregate counts from the public stats endpoint. Returns null until the API
 * answers (or if it fails) — callers render the static promises instead.
 */
export function useLiveStats(): LiveStats | null {
  const [stats, setStats] = useState<LiveStats | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetch(`${getApiUrl()}/api/v1/home-safety/enquiries/stats`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!cancelled && d && typeof d.families === "number") setStats(d);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);
  return stats;
}
