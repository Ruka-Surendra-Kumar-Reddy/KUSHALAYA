"use client";

import { MkLink as Link } from "./MkLink";

import { BROCHURE_HREF, PACKAGES_HREF, SAFE_HOMES_HREF, VISION_HREF } from "@/lib/marketing/family-contacts";
import { withPublicBrand, publicSafetyScoreName } from "@/lib/public-brand";
import { EnquiryForm } from "./EnquiryForm";
import { MarketingShell } from "./MarketingShell";
import { CALLBACK_PROMISE, useSiteConfig, whatsAppHref } from "@/lib/marketing/site-config";
import { ICONS, PageHero, Reveal, SectionHead } from "./ui";

const EXPECT = [
  { icon: "check", title: "Free", body: "No payment, no obligation. The home assessment is free too." },
  { icon: "clock", title: "A short form", body: "A few minutes on your phone or laptop — from anywhere." },
  { icon: "chat", title: "A call back", body: `${CALLBACK_PROMISE} to talk it through and, if it helps, book a home visit.` },
] as const;

const STEPS = [
  {
    tag: "Screen",
    title: "KushCare Discovery",
    body: "You tell us about your loved one and we call you back to understand their situation — the screening step CDC STEADI starts with.",
  },
  {
    tag: "Assess",
    title: "Home visit",
    body: withPublicBrand("A respectful LiveWell360 assessment of lighting, bathrooms, stairs, mobility and daily safety — scored out of 100."),
  },
  {
    tag: "Intervene",
    title: "Improve & support",
    body: "Prioritised recommendations, wearable SOS when needed, physiotherapy and a KushLife check on every visit.",
  },
] as const;

const OFFER = [
  "KushCare Discovery (you are here)",
  `${publicSafetyScoreName()} out of 100`,
  "A personalised safety report for the family",
  "Recommended improvements with clear next steps",
  "Wearable SOS when the home needs it",
  "Family portal updates — including for relatives abroad",
  "A KushLife check on every visit, and an annual review",
] as const;

export function ParentCareCheckMarketingPage() {
  const site = useSiteConfig();
  const paid = site.assessment_is_paid;
  /** With a paid home visit, never call the whole thing "free" — only sending the form is. */
  const priceLine = `Sending this form is free; the home visit costs ${site.assessment_price_label} if you book it.`;
  const offer = paid ? OFFER : ["Free KushCare Discovery (you are here)", ...OFFER.slice(1)];
  return (
    <MarketingShell primaryCtaHref="#care-check-form" primaryCtaLabel="Request a call back">
      <PageHero
        eyebrow={paid ? "A few minutes" : "Free · A few minutes"}
        title="KushCare Discovery."
        accent="A respectful first step."
        lede="Tell us about your loved one — a parent, spouse, grandparent or yourself — and we'll advise whether a full home assessment is the right next step — without judgement, and with dignity intact. Families abroad can complete it just as easily."
        image="/marketing/care-check-hero.webp"
        imageAlt="A daughter filling in a form on her phone beside her smiling mother on the sofa"
      >
        <a className="mk-btn mk-btn-primary mk-btn-lg" href="#care-check-form">
          {paid ? "Request a call back" : "Request a free call back"} {ICONS.arrow}
        </a>
        <Link className="mk-btn mk-btn-outline mk-btn-lg" href={SAFE_HOMES_HREF}>
          Why falls matter
        </Link>
      </PageHero>

      <section className="mk-band" aria-labelledby="expect-title">
        <div className="mk-wrap">
          <SectionHead id="expect-title" eyebrow="What to expect" title={paid ? "Simple and quick" : "Simple, quick and free"} />
          <div className="mk-grid-3">
            {EXPECT.map((e, i) => (
              <Reveal key={e.title} className="mk-card" as="article" delay={i * 80}>
                <span className={`mk-card-ico ${i === 1 ? "is-gold" : i === 2 ? "is-green" : ""}`}>
                  {ICONS[e.icon]}
                </span>
                <h3>{i === 0 && paid ? "Free to send" : e.title}</h3>
                <p>{i === 0 && paid ? priceLine : e.body}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="mk-band mk-band-soft" id="care-check-form" aria-labelledby="pcc-form-title">
        <div className="mk-wrap mk-contact-grid">
          <Reveal>
            <p className="mk-eyebrow">About your loved one</p>
            <h2 id="pcc-form-title">Request your KushCare Discovery</h2>
            <p className="mk-sub">
              Share a few details — their living situation, what worries you, and who we should
              contact. {CALLBACK_PROMISE}, with clear next steps.
            </p>
            <p className="mk-note">
              {paid ? (
                priceLine
              ) : (
                <>
                  KushCare Discovery: <span className="mk-price-chip">{site.assessment_price_label}</span>
                </>
              )}
            </p>
            <ul className="mk-checklist">
              {offer.map((o) => (
                <li key={o}>{o}</li>
              ))}
            </ul>
            <p className="mk-note" style={{ marginTop: "1rem" }}>
              Printables: <Link href={VISION_HREF}>Vision sheet</Link> ·{" "}
              <Link href={BROCHURE_HREF}>Brochure</Link> · <Link href={PACKAGES_HREF}>Plans</Link>
            </p>
            <p style={{ marginTop: "1rem" }}>
              <a
                className="mk-btn mk-btn-green"
                href={whatsAppHref(site, "Hi, I'd like to book a KushCare Discovery home assessment.")}
                target="_blank"
                rel="noopener noreferrer"
              >
                {ICONS.whatsapp} Prefer WhatsApp? Message us
              </a>
            </p>
          </Reveal>
          <Reveal delay={120} className="mk-form-card">
            <EnquiryForm kind="care-check" submitLabel="Start my KushCare Discovery" />
          </Reveal>
        </div>
      </section>

      <section className="mk-band" aria-labelledby="pcc-path-title">
        <div className="mk-wrap">
          <SectionHead
            id="pcc-path-title"
            eyebrow="Screen · Assess · Intervene"
            title="What happens after the check"
            sub="Inspired by the STEADI idea of screen, assess and intervene — delivered with a respectful visit and a clear family plan. We are not endorsed by or affiliated with CDC or AARP."
          />
          <div className="mk-steps-3">
            {STEPS.map((s, i) => (
              <Reveal key={s.tag} className="mk-step-card" as="article" delay={i * 90}>
                <span className="mk-step-n">{String(i + 1).padStart(2, "0")}</span>
                <small>{s.tag}</small>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}
