"use client";

import { useState } from "react";
import { MkLink as Link } from "./MkLink";

import { PARTNERS_HREF } from "@/lib/marketing/family-contacts";
import { withPublicBrand } from "@/lib/public-brand";
import { MarketingShell } from "./MarketingShell";
import { partnerEnquiryHref } from "./PartnersMarketingPage";
import { EMAILS, mailtoHref } from "@/lib/marketing/family-contacts";
import { ICONS, PageHero, Reveal, SectionHead } from "./ui";

const PATHS = [
  {
    title: "Product suppliers",
    icon: "tool",
    body: "Bathroom safety, grab bars, anti-slip, lighting, mobility aids, wearable SOS and related products suited to Indian homes.",
  },
  {
    title: "Installers & field teams",
    icon: "shield",
    body: "Verified professionals who complete approved changes with photos, notes and respect for the elder in the home.",
  },
  {
    title: "Physiotherapists & nurses",
    icon: "heart",
    body: "Home visits that keep someone steady and well — with progress shared on the family portal.",
  },
] as const;

const STEPS = [
  { title: "Enquire", body: "Message us with your company, category and the areas you cover." },
  { title: "Capability review", body: "We learn how you work — products, quality, timelines and how you treat families." },
  { title: "Alignment", body: "If there is a fit, we agree on introductions, documentation and Trusted Partner recognition." },
  { title: "Serve together", body: "Assessment-led jobs, clear scopes and co-branded delivery families can trust." },
] as const;

const FAQS = [
  {
    q: "Is this a paid listing?",
    a: "No. Founding partners are invited on capability and fit — not a catalogue fee. Commercial terms stay transparent for families.",
  },
  {
    q: "Do you guarantee a volume of leads?",
    a: "No. We introduce partners when assessments call for your category. Quality of fit matters more than inflated lead counts.",
  },
  {
    q: withPublicBrand("Can we use the LiveWell360 name?"),
    a: "Approved Trusted Partners may use agreed co-brand recognition. Unapproved use of our name or logo is not allowed.",
  },
  {
    q: "What happens after I message you?",
    a: "We reply, ask a few practical questions, and set up a short call if there is potential alignment.",
  },
] as const;

export function BecomePartnerMarketingPage() {
  const enquiry = partnerEnquiryHref();
  const [open, setOpen] = useState<number | null>(0);
  return (
    <MarketingShell primaryCtaHref={enquiry} primaryCtaLabel="Partner enquiry">
      <PageHero
        eyebrow="Become a partner"
        title="Grow with families who already trust the plan."
        lede="Join the Trusted Partner Network as a supplier, installer or therapist. You get assessment-led work and co-branded recognition — families get verified, documented delivery."
        image="/marketing/become-partner.webp"
        imageAlt="A shop owner shaking hands with a Family Partner at a counter of bathroom safety products"
      >
        <a className="mk-btn mk-btn-green mk-btn-lg" href={enquiry} target="_blank" rel="noopener noreferrer">
          {ICONS.whatsapp} Enquire on WhatsApp
        </a>
        <Link className="mk-btn mk-btn-outline mk-btn-lg" href={PARTNERS_HREF}>
          See the network
        </Link>
      </PageHero>

      <section className="mk-band" aria-labelledby="paths-title">
        <div className="mk-wrap">
          <SectionHead id="paths-title" eyebrow="Who should apply" title="Three ways to partner" />
          <div className="mk-grid-3">
            {PATHS.map((p, i) => (
              <Reveal key={p.title} className="mk-card" as="article" delay={i * 80}>
                <span className={`mk-card-ico ${i === 1 ? "is-green" : i === 2 ? "is-gold" : ""}`}>
                  {ICONS[p.icon]}
                </span>
                <h3>{p.title}</h3>
                <p>{p.body}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="mk-band mk-band-soft" aria-labelledby="process-title">
        <div className="mk-wrap">
          <SectionHead id="process-title" eyebrow="How it works" title="Four simple steps" />
          <div className="mk-grid-4">
            {STEPS.map((s, i) => (
              <Reveal key={s.title} className="mk-step-card" as="article" delay={i * 80}>
                <span className="mk-step-n">{String(i + 1).padStart(2, "0")}</span>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="mk-band" aria-labelledby="partner-faq-title">
        <div className="mk-wrap">
          <SectionHead id="partner-faq-title" eyebrow="Questions" title="What partners ask first" />
          <div className="mk-faq">
            {FAQS.map((item, i) => {
              const isOpen = open === i;
              return (
                <div key={item.q} className={isOpen ? "mk-faq-item is-open" : "mk-faq-item"}>
                  <h3>
                    <button
                      type="button"
                      className="mk-faq-q"
                      aria-expanded={isOpen}
                      onClick={() => setOpen(isOpen ? null : i)}
                    >
                      {item.q}
                      {ICONS.plus}
                    </button>
                  </h3>
                  {isOpen ? <p className="mk-faq-a">{item.a}</p> : null}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section className="mk-band mk-band-navy mk-on-dark mk-cta" aria-labelledby="apply-title">
        <div className="mk-wrap">
          <Reveal className="mk-cta-inner">
            <h2 id="apply-title">Start with a conversation</h2>
            <p className="mk-lede">
              Share your company name, what you supply or install, and the areas you cover. We&rsquo;ll
              take it from there.
            </p>
            <div className="mk-actions">
              <a className="mk-btn mk-btn-white mk-btn-lg" href={enquiry} target="_blank" rel="noopener noreferrer">
                {ICONS.whatsapp} Partner enquiry on WhatsApp
              </a>
              <a className="mk-btn mk-btn-glass mk-btn-lg" href={mailtoHref(EMAILS.sales, "Partner enquiry")}>
                {ICONS.mail} {EMAILS.sales}
              </a>
            </div>
          </Reveal>
        </div>
      </section>
    </MarketingShell>
  );
}
