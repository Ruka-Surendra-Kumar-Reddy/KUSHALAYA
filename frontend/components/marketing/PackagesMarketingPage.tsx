"use client";

import { MkLink as Link } from "./MkLink";

import { EMAILS, PARENT_CARE_CHECK_HREF, mailtoHref } from "@/lib/marketing/family-contacts";
import { MarketingShell } from "./MarketingShell";
import { CarePlans } from "./CarePlans";
import { SafetyProducts } from "./SafetyProducts";
import { CustomPlanBuilder } from "./CustomPlanBuilder";
import { ICONS, PageHero, Photo, Reveal, SectionHead } from "./ui";

const WEARABLE_ALERTS = [
  {
    title: "SOS button",
    icon: "bell",
    body: "A press on the wearable sends a critical alert to the family portal — so relatives know within seconds, not after a missed call.",
  },
  {
    title: "Immobility warning",
    icon: "clock",
    body: "When the band is online but shows no daytime movement for a set window, the family gets a warning — distinct from SOS, never confused with a switched-off band.",
  },
  {
    title: "Possible-fall alert",
    icon: "shield",
    body: "Experimental fall sensing can nudge the family to check in. It is not a medical device — confirm in person when it matters.",
  },
] as const;

export function PackagesMarketingPage() {
  return (
    <MarketingShell>
      <PageHero
        eyebrow="Plans & pricing"
        title="Elder care plans and prices."
        accent="Clear, no surprises."
        lede="KushAlaya elder care plans cost ₹55,000 to ₹1,60,000 a year, or ₹6,000 to ₹17,500 a month, GST included. Each of the four plans brings 8 to 70 care-manager visits a year and the family app; Privilege and Signature add an SOS watch."
        image="/marketing/plans-hero.webp"
        imageAlt="A care manager organising a weekly pill box with an elderly couple at their kitchen table"
      >
        <a className="mk-btn mk-btn-primary mk-btn-lg" href="#plans">
          Compare plans
        </a>
        <a className="mk-btn mk-btn-outline mk-btn-lg" href="#custom-plan">
          Build your own
        </a>
      </PageHero>

      <CarePlans
        ctaHref={PARENT_CARE_CHECK_HREF}
        onRequestCustom={() => {
          document.getElementById("custom-plan")?.scrollIntoView({ behavior: "smooth", block: "start" });
        }}
      />

      <section className="mk-band" aria-labelledby="physio-title">
        <div className="mk-wrap mk-two-col">
          <Reveal>
            <Photo
              src="/marketing/physio.webp"
              alt="A physiotherapist guiding an elderly woman through a sit-to-stand exercise at home"
            />
          </Reveal>
          <Reveal delay={120}>
            <p className="mk-eyebrow">Physiotherapy at home</p>
            <h2 id="physio-title">Strength and balance are what keep someone at home</h2>
            <p className="mk-sub">
              Book physiotherapy sessions at home when they&rsquo;re needed. Progress shows up in
              the KushLife &ldquo;Steady&rdquo; check on every visit.
            </p>
          </Reveal>
        </div>
      </section>

      <section className="mk-band mk-band-soft" aria-labelledby="wear-title">
        <div className="mk-wrap">
          <SectionHead
            id="wear-title"
            eyebrow="Wearable care alerts"
            title="SOS, immobility and possible‑fall — on the family portal"
            sub="Privilege and Signature include a complimentary SOS watch with family alerts. Alerts arrive in calm, plain language — not a wall of sensor noise."
          />
          <div className="mk-grid-3">
            {WEARABLE_ALERTS.map((a, i) => (
              <Reveal key={a.title} className="mk-card" as="article" delay={i * 80}>
                <span className={`mk-card-ico ${i === 1 ? "is-gold" : i === 2 ? "is-green" : ""}`}>
                  {ICONS[a.icon]}
                </span>
                <h3>{a.title}</h3>
                <p>{a.body}</p>
              </Reveal>
            ))}
          </div>
          <p className="mk-note" style={{ marginTop: "1rem" }}>
            Possible-fall detection is experimental and not medical-grade. A switched-off band shows
            as offline, never as immobility.
          </p>
        </div>
      </section>

      <SafetyProducts ctaHref={PARENT_CARE_CHECK_HREF} />

      <CustomPlanBuilder />

      <section className="mk-band mk-band-navy mk-on-dark mk-cta" aria-labelledby="pkg-cta-title">
        <div className="mk-wrap">
          <Reveal className="mk-cta-inner">
            <h2 id="pkg-cta-title">Not sure which plan fits?</h2>
            <p className="mk-lede">
              Start with the home assessment. We&rsquo;ll recommend a plan and only the products the
              home actually needs — with a written quote before anything is fitted.
            </p>
            <div className="mk-actions">
              <Link className="mk-btn mk-btn-white mk-btn-lg" href={PARENT_CARE_CHECK_HREF}>
                Book an assessment
              </Link>
              <a className="mk-btn mk-btn-glass mk-btn-lg" href={mailtoHref(EMAILS.sales, "Plans and pricing")}>
                {ICONS.mail} {EMAILS.sales}
              </a>
            </div>
          </Reveal>
        </div>
      </section>
    </MarketingShell>
  );
}
