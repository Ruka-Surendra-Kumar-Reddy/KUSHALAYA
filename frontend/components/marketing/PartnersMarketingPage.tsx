"use client";

import { MkLink as Link } from "./MkLink";

import {
  BECOME_A_PARTNER_HREF,
  familyWhatsAppDigits,
  partnerWhatsAppHref,
} from "@/lib/marketing/family-contacts";
import { founderWhatsAppHref } from "@/lib/marketing/founder";
import { withPublicBrand } from "@/lib/public-brand";
import { MarketingShell } from "./MarketingShell";
import { EMAILS, mailtoHref } from "@/lib/marketing/family-contacts";
import { ICONS, PageHero, Photo, Reveal, SectionHead, type IconName } from "./ui";

/** Partner enquiries go to the business WhatsApp when configured, else to the founder. */
export function partnerEnquiryHref(): string {
  if (familyWhatsAppDigits()) return partnerWhatsAppHref();
  return founderWhatsAppHref(
    withPublicBrand("Hi — I'm interested in joining the LiveWell360 Trusted Partner Network as a supplier or installer."),
  );
}

const BENEFITS: { icon: IconName; title: string; body: string }[] = [
  {
    icon: "clipboard",
    title: "Assessment-qualified work",
    body: withPublicBrand("Families come to you after a LiveWell360 home assessment — with a clear scope, not a cold enquiry."),
  },
  {
    icon: "shield",
    title: "Co-branded trust",
    body: withPublicBrand("Approved partners use the LiveWell360 Trusted Partner recognition with families who already know our process."),
  },
  {
    icon: "star",
    title: "Recommended where it fits",
    body: "When a plan calls for your category — bathroom safety, mobility, smart safety or installation — we introduce matched partners.",
  },
  {
    icon: "doc",
    title: "Documented delivery",
    body: "Completion notes and photos give families confidence — and credit the partner who did the work.",
  },
];

const CATEGORIES = [
  "Bathroom safety",
  "Home modifications",
  "Smart home & emergency",
  "Medical equipment",
  "Home healthcare",
  "Physiotherapy & nursing",
  "Home maintenance",
  "Apartment communities",
] as const;

const STANDARDS = [
  "Capability and credentials reviewed before any introduction",
  "Transparent estimates — no surprise mark-ups for families",
  "Respectful conduct with elders on every visit",
  "Documented completion with photos",
  "Open to feedback after every job",
] as const;

export function PartnersMarketingPage() {
  const enquiry = partnerEnquiryHref();
  return (
    <MarketingShell primaryCtaHref={BECOME_A_PARTNER_HREF} primaryCtaLabel="Become a partner">
      <PageHero
        eyebrow="Trusted Partner Network"
        title="Partners families can trust."
        accent="A network worth joining."
        lede={withPublicBrand(
          "LiveWell360 connects families with verified suppliers, installers and therapists — after a professional assessment, not a sales pitch. Partners gain qualified work and co-branded recognition; families gain accountable delivery.",
        )}
        image="/marketing/partner-install.webp"
        imageAlt="Two installers fitting a fold-up toilet rail in a bathroom, with a checklist on a tablet"
      >
        <Link className="mk-btn mk-btn-primary mk-btn-lg" href={BECOME_A_PARTNER_HREF}>
          Become a partner
        </Link>
        <a className="mk-btn mk-btn-green mk-btn-lg" href={enquiry} target="_blank" rel="noopener noreferrer">
          {ICONS.whatsapp} Enquire on WhatsApp
        </a>
      </PageHero>

      <section className="mk-band" aria-labelledby="value-title">
        <div className="mk-wrap">
          <SectionHead
            id="value-title"
            eyebrow="Why partner with us"
            title="Value that goes both ways"
            sub="We bring assessment-led demand and a calm, respectful brand. You bring reliable products, careful installation and service families can count on."
          />
          <div className="mk-grid-4">
            {BENEFITS.map((b, i) => (
              <Reveal key={b.title} className="mk-card" as="article" delay={i * 70}>
                <span className={`mk-card-ico ${i % 2 ? "is-green" : ""}`}>{ICONS[b.icon]}</span>
                <h3>{b.title}</h3>
                <p>{b.body}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="mk-band mk-band-soft" aria-labelledby="standards-title">
        <div className="mk-wrap mk-two-col">
          <Reveal>
            <Photo
              src="/marketing/partners.webp"
              alt="A physiotherapist, an installer and a care manager talking with an elderly couple"
            />
          </Reveal>
          <Reveal delay={120}>
            <p className="mk-eyebrow">Who we work with</p>
            <h2 id="standards-title">Recognition earned, not bought</h2>
            <ul className="mk-chips">
              {CATEGORIES.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
            <ul className="mk-checklist" style={{ marginTop: "1.5rem" }}>
              {STANDARDS.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
            <p className="mk-note" style={{ marginTop: "1rem" }}>
              The network is forming now. Public partner profiles will appear here as real
              partnerships are made — we won&rsquo;t show logos or claims ahead of them.
            </p>
          </Reveal>
        </div>
      </section>

      <section className="mk-band mk-band-navy mk-on-dark mk-cta" aria-labelledby="partner-cta-title">
        <div className="mk-wrap">
          <Reveal className="mk-cta-inner">
            <h2 id="partner-cta-title">{withPublicBrand("Ready to co-brand with LiveWell360?")}</h2>
            <p className="mk-lede">
              Tell us what you supply, install or provide. We&rsquo;ll explain how the network works
              and whether there is a fit.
            </p>
            <div className="mk-actions">
              <Link className="mk-btn mk-btn-white mk-btn-lg" href={BECOME_A_PARTNER_HREF}>
                Become a partner
              </Link>
              <a className="mk-btn mk-btn-glass mk-btn-lg" href={enquiry} target="_blank" rel="noopener noreferrer">
                {ICONS.whatsapp} WhatsApp enquiry
              </a>
              <a className="mk-btn mk-btn-glass mk-btn-lg" href={mailtoHref(EMAILS.sales, "Trusted Partner Network")}>
                {ICONS.mail} {EMAILS.sales}
              </a>
            </div>
          </Reveal>
        </div>
      </section>
    </MarketingShell>
  );
}
