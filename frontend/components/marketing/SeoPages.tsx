"use client";

/**
 * Templates for the SEO landing pages: /faq, /services/<slug>, /elder-care/<city>.
 * Copy lives in lib/marketing/seo-*.ts; styles in app/marketing/seo-pages.css.
 */
import { useState, type ReactNode } from "react";

import { MkLink as Link } from "./MkLink";
import { MarketingShell } from "./MarketingShell";
import { ICONS, PageHero, Reveal, SectionHead } from "./ui";
import { PARENT_CARE_CHECK_HREF } from "@/lib/marketing/family-contacts";
import { SEO_EMERGENCY_LINE, SEO_PHONES, SEO_PRICE_LINE, type SeoSection } from "@/lib/marketing/seo-common";
import { SEO_FAQ_GROUPS } from "@/lib/marketing/seo-faq";
import { PLAN_COST_ANSWER } from "@/lib/marketing/plans";
import { SEO_SERVICES, seoServiceBySlug } from "@/lib/marketing/seo-services";
import { SEO_CITIES, seoCityBySlug } from "@/lib/marketing/seo-cities";
import "@/app/marketing/seo-pages.css";

/** Sidebar card: one booking button plus call and WhatsApp (sticky on desktop with the aside). */
function AsideCta({ title }: { title: string }) {
  const wa = `https://wa.me/${SEO_PHONES.india.tel.replace(/\D/g, "")}`;
  return (
    <div className="seo-links seo-aside-cta">
      <h2>{title}</h2>
      <Link className="mk-btn mk-btn-primary" href={PARENT_CARE_CHECK_HREF}>
        Book KushCare Discovery
      </Link>
      <a className="mk-btn mk-btn-outline" href={SEO_PHONES.india.tel}>
        {ICONS.phone} Call {SEO_PHONES.india.display}
      </a>
      <a className="mk-btn mk-btn-green" href={wa} target="_blank" rel="noopener noreferrer">
        {ICONS.whatsapp} WhatsApp us
      </a>
      <a className="seo-aside-us" href={SEO_PHONES.usCanada.tel}>
        US &amp; Canada: {SEO_PHONES.usCanada.display}
      </a>
    </div>
  );
}

function Prose({ sections }: { sections: readonly SeoSection[] }) {
  return (
    <div className="seo-prose">
      {sections.map((s) => (
        <Reveal key={s.title} as="section">
          <h2>{s.title}</h2>
          {s.paras.map((p) => (
            <p key={p}>{p}</p>
          ))}
          {s.bullets?.length ? (
            <ul className="mk-checklist">
              {s.bullets.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          ) : null}
        </Reveal>
      ))}
    </div>
  );
}

function LinkList({ title, links }: { title: string; links: readonly { href: string; label: string }[] }) {
  return (
    <nav className="seo-links" aria-label={title}>
      <h2>{title}</h2>
      <ul>
        {links.map((l) => (
          <li key={l.href}>
            <Link href={l.href}>
              {l.label} {ICONS.arrow}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function SeoCta({ title, body }: { title: string; body: ReactNode }) {
  return (
    <section className="mk-band mk-band-navy mk-on-dark mk-cta seo-cta" aria-labelledby="seo-cta-title">
      <div className="mk-wrap">
        <Reveal className="mk-cta-inner">
          <h2 id="seo-cta-title">{title}</h2>
          <p className="mk-lede">{body}</p>
          <div className="mk-actions">
            <Link className="mk-btn mk-btn-white mk-btn-lg" href={PARENT_CARE_CHECK_HREF}>
              Start KushCare Discovery {ICONS.arrow}
            </Link>
            <a className="mk-btn mk-btn-glass mk-btn-lg" href={SEO_PHONES.india.tel}>
              India {SEO_PHONES.india.display}
            </a>
            <a className="mk-btn mk-btn-glass mk-btn-lg" href={SEO_PHONES.usCanada.tel}>
              US/Canada {SEO_PHONES.usCanada.display}
            </a>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

const SERVICE_LINKS = SEO_SERVICES.map((s) => ({ href: `/services/${s.slug}`, label: s.label }));
const CITY_LINKS = SEO_CITIES.map((c) => ({ href: `/elder-care/${c.slug}`, label: `Elder care in ${c.name}` }));

/* --- /faq ------------------------------------------------------------------ */

export function SeoFaqPage() {
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const groups = SEO_FAQ_GROUPS.map((g) => ({
    ...g,
    items: q ? g.items.filter((f) => `${f.q} ${f.a}`.toLowerCase().includes(q)) : g.items,
  })).filter((g) => g.items.length);
  return (
    <MarketingShell>
      <PageHero
        eyebrow="Questions & answers"
        title="Frequently asked questions"
        lede={`${PLAN_COST_ANSWER} KushCare Discovery is free. Answers on visits, safety and privacy below.`}
      >
        <Link className="mk-btn mk-btn-primary mk-btn-lg" href={PARENT_CARE_CHECK_HREF}>
          Start KushCare Discovery {ICONS.arrow}
        </Link>
        <Link className="mk-btn mk-btn-ghost mk-btn-lg" href="/contact">
          Ask us something else
        </Link>
      </PageHero>

      <section className="mk-band" aria-label="Frequently asked questions">
        <div className="mk-wrap">
          <nav className="seo-chips" aria-label="FAQ topics">
            {SEO_FAQ_GROUPS.map((g) => (
              <a key={g.id} href={`#${g.id}`}>
                {g.title}
              </a>
            ))}
          </nav>
          <div className="seo-layout">
          <div className="seo-faq-main">
          <label className="seo-faq-search">
            <span className="mk-sr">Search the questions</span>
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search the questions, e.g. price, NRI, SOS"
            />
          </label>
          {q && !groups.length ? (
            <p className="mk-note">No question matches that. Call or WhatsApp us and we&rsquo;ll answer it.</p>
          ) : null}
          {groups.map((g) => (
            <div key={g.id} className="seo-faq-group">
              <h2 id={g.id}>{g.title}</h2>
              <div className="mk-faq">
                {g.items.map((f) => (
                  <details key={f.q} className="mk-faq-item seo-faq-item">
                    <summary className="mk-faq-q">
                      <span>{f.q}</span>
                      {ICONS.plus}
                    </summary>
                    <p className="mk-faq-a">{f.a}</p>
                  </details>
                ))}
              </div>
            </div>
          ))}
          </div>
          <aside className="seo-aside">
            <AsideCta title="Still unsure? Talk to us" />
          </aside>
          </div>
        </div>
      </section>

      <section className="mk-band mk-band-soft" aria-label="More about our services">
        <div className="mk-wrap seo-link-grid">
          <LinkList title="Our services" links={SERVICE_LINKS} />
          <LinkList title="Cities we serve" links={CITY_LINKS} />
        </div>
      </section>

      <SeoCta title="Still have a question?" body="Fill in the KushCare Discovery form and we will call you back, or call us now." />
    </MarketingShell>
  );
}

/* --- /services/<slug> ------------------------------------------------------- */

export function SeoServicePage({ slug }: { slug: string }) {
  const s = seoServiceBySlug(slug);
  if (!s) return null;
  const others = SERVICE_LINKS.filter((l) => l.href !== `/services/${s.slug}`);
  return (
    <MarketingShell>
      <PageHero eyebrow={s.eyebrow} title={s.title} accent={s.accent} lede={s.lede} image={s.image} imageAlt={s.imageAlt}>
        <Link className="mk-btn mk-btn-primary mk-btn-lg" href={PARENT_CARE_CHECK_HREF}>
          Start KushCare Discovery {ICONS.arrow}
        </Link>
        <Link className="mk-btn mk-btn-ghost mk-btn-lg" href="/packages">
          See plans
        </Link>
      </PageHero>

      <section className="mk-band" aria-label={s.eyebrow}>
        <div className="mk-wrap seo-layout">
          <Prose sections={s.sections} />
          <aside className="seo-aside">
            <AsideCta title="Book or ask a question" />
            <LinkList title="Related" links={s.related} />
            <LinkList title="Other services" links={others} />
          </aside>
        </div>
      </section>

      <SeoCta
        title="Start with a KushCare Discovery"
        body="Tell us about your parent and their home. We call you back and arrange what they need."
      />
    </MarketingShell>
  );
}

/* --- /elder-care/<city> ----------------------------------------------------- */

export function SeoCityPage({ slug }: { slug: string }) {
  const c = seoCityBySlug(slug);
  if (!c) return null;
  const otherCities = CITY_LINKS.filter((l) => l.href !== `/elder-care/${c.slug}`);
  const related = [
    ...SERVICE_LINKS,
    ...(c.blogSlug && c.blogTitle ? [{ href: `/blog/${c.blogSlug}`, label: c.blogTitle }] : []),
  ];
  const sections: SeoSection[] = [
    {
      title: `Homes in ${c.name}`,
      paras: [c.homes.intro],
      bullets: c.homes.points,
    },
    {
      title: `Weather and safety in ${c.name}`,
      paras: [c.climate.intro],
      bullets: c.climate.points,
    },
    {
      title: "When the family lives far away",
      paras: [
        c.family,
        "After every visit you get an update in the family app, and calls with your care manager are planned around your time zone.",
      ],
    },
    {
      title: `What we usually look at first in ${c.name} homes`,
      paras: ["Every home is different and the assessment decides the plan, but in this city we often start with:"],
      bullets: c.firstChecks,
    },
    {
      title: "How it works",
      paras: [
        `We work with families across India and arrange visits in ${c.name}. Start with the KushCare Discovery form; we call you back, then arrange a home safety assessment with a KushAlaya Safety Score, the fixes your parents' home needs, and regular caregiver visits with four KushLife checks every time.`,
        `${SEO_PRICE_LINE} ${SEO_EMERGENCY_LINE}`,
      ],
    },
  ];
  return (
    <MarketingShell>
      <PageHero
        eyebrow={`Elder care in ${c.name}${c.alsoKnownAs ? ` (${c.alsoKnownAs})` : ""}`}
        title={`Elder care at home in ${c.name},`}
        accent=" wherever you live."
        lede={c.lede}
        image="/marketing/contact-team.webp"
        imageAlt="Three care team members in uniform outside a family home"
      >
        <Link className="mk-btn mk-btn-primary mk-btn-lg" href={PARENT_CARE_CHECK_HREF}>
          Start KushCare Discovery {ICONS.arrow}
        </Link>
        <Link className="mk-btn mk-btn-ghost mk-btn-lg" href="/contact">
          Talk to us
        </Link>
      </PageHero>

      <section className="mk-band" aria-label={`Elder care in ${c.name}`}>
        <div className="mk-wrap seo-layout">
          <Prose sections={sections} />
          <aside className="seo-aside">
            <AsideCta title="Book or ask a question" />
            <LinkList title="Our services" links={related} />
            <LinkList title="Other cities" links={otherCities} />
          </aside>
        </div>
      </section>

      <SeoCta
        title={`Arrange a home safety check in ${c.name}`}
        body="Fill in the KushCare Discovery form and we will call you back to plan the visit."
      />
    </MarketingShell>
  );
}
