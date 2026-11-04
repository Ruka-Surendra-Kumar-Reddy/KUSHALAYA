"use client";

import { PhoneText } from "./PhoneText";
import { BRAND_ASSETS } from "@/lib/brand-assets";
import { MkLink as Link } from "./MkLink";

import { CONTACT_HREF, PARENT_CARE_CHECK_HREF, US_PHONE } from "@/lib/marketing/family-contacts";
import {
  FOUNDER,
  KUSHLIFE,
  founderMailtoHref,
  founderWhatsAppHref,
} from "@/lib/marketing/founder";
import { publicBrandName } from "@/lib/public-brand";
import { MarketingShell } from "./MarketingShell";
import { ICONS, Photo, Reveal, SectionHead, type IconName } from "./ui";

/**
 * What the company stands for, in the founder's frame. These restate
 * commitments already made elsewhere on the site (prevention, dignity, one
 * accountable team, the family always informed) — no biography is invented
 * here; the founder's own words come only from lib/marketing/founder.ts.
 */
const COMMITMENTS: { icon: IconName; tone: string; title: string; body: string }[] = [
  {
    icon: "shield",
    tone: "",
    title: "Act before something goes wrong",
    body: "Prevention first: a scored home assessment and a check on every visit, so a fall is avoided rather than reported.",
  },
  {
    icon: "heart",
    tone: "is-green",
    title: "Dignity is not optional",
    body: "Nothing is done to an elder that they have not agreed to. Options are explained in plain language, at their pace.",
  },
  {
    icon: "users",
    tone: "is-gold",
    title: "One team, fully accountable",
    body: "Assessment, installation and ongoing care from one team — not a box left at the door and a number to call.",
  },
  {
    icon: "globe",
    tone: "",
    title: "The family always knows",
    body: "Photos, notes and the KushLife trend after every visit, for every member of the family, wherever they live.",
  },
];

function ContactCards() {
  return (
    <div className="mk-founder-contact">
      <p className="mk-founder-contact-title">{FOUNDER.invite}</p>
      <a className="mk-contact-link" href={FOUNDER.phoneTel}>
        <span className="mk-card-ico">{ICONS.phone}</span>
        <span>
          <small>Call</small>
          <strong><PhoneText value={FOUNDER.phoneDisplay} /></strong>
        </span>
      </a>
      <a className="mk-contact-link" href={US_PHONE.tel}>
        <span className="mk-card-ico">{ICONS.phone}</span>
        <span>
          <small>From the US &amp; Canada</small>
          <strong>{US_PHONE.display}</strong>
        </span>
      </a>
      <a
        className="mk-contact-link"
        href={founderWhatsAppHref()}
        target="_blank"
        rel="noopener noreferrer"
      >
        <span className="mk-card-ico is-green">{ICONS.whatsapp}</span>
        <span>
          <small>WhatsApp</small>
          <strong>Message me</strong>
        </span>
      </a>
      <a className="mk-contact-link" href={founderMailtoHref()} style={{ gridColumn: "1 / -1" }}>
        <span className="mk-card-ico is-gold">{ICONS.mail}</span>
        <span>
          <small>Email</small>
          <strong>{FOUNDER.email}</strong>
        </span>
      </a>
    </div>
  );
}

export function FounderMarketingPage() {
  return (
    <MarketingShell>
      {/* Portrait + the founder's own words */}
      <section className="mk-hero mk-founder-hero" id="top">
        <div className="mk-wrap mk-founder-grid">
          <Reveal as="figure" className="mk-founder-figure">
            {/* eslint-disable-next-line @next/next/no-img-element -- static marketing asset */}
            <img
              src={FOUNDER.photo}
              srcSet={`${FOUNDER.photoSmall} 450w, ${FOUNDER.photo} 900w`}
              sizes="(min-width: 900px) 420px, 90vw"
              alt={FOUNDER.photoAlt}
              width={900}
              height={1125}
              fetchPriority="high"
              decoding="async"
            />
            <figcaption className="mk-founder-badge">
              {/* eslint-disable-next-line @next/next/no-img-element -- static brand mark */}
              <img className="mk-founder-badge-mark" src={BRAND_ASSETS.header} alt="" width={44} height={44} />
              <span>
                <strong>{FOUNDER.name}</strong>
                <span>{FOUNDER.role}</span>
              </span>
            </figcaption>
          </Reveal>

          <Reveal delay={120} className="mk-founder-copy">
            <p className="mk-eyebrow">From the founder</p>
            <h1 className="mk-founder-quote">{FOUNDER.tagline}</h1>
            {FOUNDER.statement.map((para) => (
              <p key={para} className="mk-founder-para">
                {para}
              </p>
            ))}
            <p className="mk-founder-sign">{FOUNDER.name}</p>
            <ContactCards />
          </Reveal>
        </div>
      </section>

      {/* What we stand for */}
      <section className="mk-band mk-band-soft" aria-labelledby="stand-title">
        <div className="mk-wrap">
          <SectionHead
            id="stand-title"
            eyebrow="What we stand for"
            title={`The promises ${publicBrandName()} is built on`}
            sub="Four commitments every family can hold us to — on the first visit and every one after."
          />
          <div className="mk-grid-4">
            {COMMITMENTS.map((c, i) => (
              <Reveal key={c.title} className="mk-card" as="article" delay={i * 80}>
                <span className={`mk-card-ico ${c.tone}`}>{ICONS[c.icon]}</span>
                <h3>{c.title}</h3>
                <p>{c.body}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* The vision, in a picture */}
      <section className="mk-band" aria-labelledby="vision-title">
        <div className="mk-wrap mk-two-col">
          <Reveal>
            <Photo
              src="/marketing/founder-scene.webp"
              alt="A sunlit verandah with a rattan chair and a cup of tea — the home a family wants their parents to keep"
              wide
            />
          </Reveal>
          <Reveal delay={120}>
            <p className="mk-eyebrow">The vision</p>
            <h2 id="vision-title">Ageing at home, safely, on their own terms</h2>
            <p className="mk-sub">
              Most parents want to stay in the home they built. The vision is simple: make that
              possible for longer — by fixing what makes a home risky, and by noticing the small
              changes in how someone is living before they become an emergency.
            </p>
            <p className="mk-sub">
              That second part is <strong>{KUSHLIFE.name}</strong>: {KUSHLIFE.strap.toLowerCase()}
            </p>
            <ul className="mk-checklist">
              {KUSHLIFE.checks.map((c) => (
                <li key={c.title}>
                  <strong>{c.title}</strong> — {c.body}
                </li>
              ))}
            </ul>
          </Reveal>
        </div>
      </section>

      {/* CTA */}
      <section className="mk-band mk-band-navy mk-on-dark mk-cta" aria-labelledby="founder-cta-title">
        <div className="mk-wrap">
          <Reveal className="mk-cta-inner">
            <h2 id="founder-cta-title">Talk to me directly</h2>
            <p className="mk-lede">
              A question, an idea, or a worry about your parents — call or message me. I read every
              message myself.
            </p>
            <div className="mk-actions">
              <a className="mk-btn mk-btn-white mk-btn-lg" href={FOUNDER.phoneTel}>
                {ICONS.phone} Call <PhoneText value={FOUNDER.phoneDisplay} />
              </a>
              <Link className="mk-btn mk-btn-glass mk-btn-lg" href={PARENT_CARE_CHECK_HREF}>
                Book an assessment
              </Link>
              <Link className="mk-btn mk-btn-glass mk-btn-lg" href={CONTACT_HREF}>
                Other ways to reach us
              </Link>
            </div>
          </Reveal>
        </div>
      </section>
    </MarketingShell>
  );
}
