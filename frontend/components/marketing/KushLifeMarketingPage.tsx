"use client";

import { MkLink as Link } from "./MkLink";

import { PACKAGES_HREF, PARENT_CARE_CHECK_HREF } from "@/lib/marketing/family-contacts";
import { KUSHLIFE } from "@/lib/marketing/founder";
import { CALLBACK_PROMISE, useSiteConfig, whatsAppHref } from "@/lib/marketing/site-config";
import { MarketingShell } from "./MarketingShell";
import { ICONS, PageHero, SectionHead } from "./ui";

/** What the family receives from KushLife, in the order it arrives. */
const RHYTHM = [
  {
    title: "After every visit",
    body: "The four checks, a short note from the caregiver and anything that needs you — in the family app the same day.",
  },
  {
    title: "Every week",
    body: "A weekly summary: how the visits went, the KushLife score and its trend, and what we're watching.",
  },
  {
    title: "Every month",
    body: "A one-page KushLife letter for each parent: what changed, what we fixed, and what we suggest next.",
  },
  {
    title: "Straight away, when it matters",
    body: "A fall, a new symptom or a safety problem doesn't wait for the summary — we call you and it shows as an alert.",
  },
] as const;

/** Screens the family app shows. Placeholders until real screenshots are added. */
const SHOTS = ["KushLife score and trend", "A visit with its four checks", "The monthly KushLife letter"] as const;
/** Flip to true once real screenshots are in public/marketing (FIX: no placeholders on the live site). */
const SHOTS_READY = false as boolean;

export function KushLifeMarketingPage() {
  const site = useSiteConfig();
  return (
    <MarketingShell>
      <PageHero
        eyebrow={KUSHLIFE.name}
        title={KUSHLIFE.strap}
        lede={KUSHLIFE.meaning}
        image="/marketing/video-call.webp"
        imageAlt="An older woman at home smiling at her grandchildren on a video call"
      >
        <Link className="mk-btn mk-btn-primary mk-btn-lg" href={PARENT_CARE_CHECK_HREF}>
          Start KushCare Discovery {ICONS.arrow}
        </Link>
        <a
          className="mk-btn mk-btn-green mk-btn-lg"
          href={whatsAppHref(site, "Hi, I'd like to know more about KushLife visits.")}
          target="_blank"
          rel="noopener noreferrer"
        >
          {ICONS.whatsapp} WhatsApp us
        </a>
      </PageHero>

      <section className="mk-band" aria-labelledby="kl-checks-title">
        <div className="mk-wrap">
          <SectionHead
            id="kl-checks-title"
            eyebrow="On every visit"
            title="Four checks, every time"
            sub="The caregiver records the same four checks on every visit, so you see a trend and not just the day something went wrong."
          />
          <ul className="mk-kl-list">
            {KUSHLIFE.checks.map((c) => (
              <li key={c.title} className="mk-kl-item">
                <h3>{c.title}</h3>
                <p>{c.body}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="mk-band mk-band-soft" aria-labelledby="kl-rhythm-title">
        <div className="mk-wrap">
          <SectionHead
            id="kl-rhythm-title"
            eyebrow="What you get"
            title="After each visit, every week, every month"
            sub="You don't have to ask how they are. It comes to you."
          />
          <ul className="mk-kl-list">
            {RHYTHM.map((r) => (
              <li key={r.title} className="mk-kl-item">
                <h3>{r.title}</h3>
                <p>{r.body}</p>
              </li>
            ))}
          </ul>
          <p style={{ marginTop: "1.25rem" }}>
            <Link className="mk-inline-link" href={PACKAGES_HREF}>
              KushLife is part of every care plan: see plans {ICONS.arrow}
            </Link>
          </p>
        </div>
      </section>

      {/* Hidden until real app screenshots exist (no "coming soon" placeholders on the live site). */}
      {SHOTS_READY ? (
      <section className="mk-band" aria-labelledby="kl-app-title">
        <div className="mk-wrap">
          <SectionHead
            id="kl-app-title"
            eyebrow="The family app"
            title="See it on your phone, wherever you live"
            sub="Your brothers and sisters can sign in too, so everyone sees the same thing."
          />
          <div className="mk-shots">
            {SHOTS.map((s) => (
              <div key={s} className="mk-shot" role="img" aria-label={`Screenshot coming soon: ${s}`}>
                <span>
                  <strong>{s}</strong>
                  <br />
                  Screenshot coming soon
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>
      ) : null}

      <section className="mk-band mk-band-navy mk-on-dark mk-cta" aria-labelledby="kl-cta-title">
        <div className="mk-wrap">
          <h2 id="kl-cta-title">KushLife starts with a KushCare Discovery visit.</h2>
          <p className="mk-lede">
            KushCare Discovery: {site.assessment_price_label}. {CALLBACK_PROMISE}.
          </p>
          <div className="mk-actions">
            <Link className="mk-btn mk-btn-white mk-btn-lg" href={PARENT_CARE_CHECK_HREF}>
              Start KushCare Discovery
            </Link>
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}
