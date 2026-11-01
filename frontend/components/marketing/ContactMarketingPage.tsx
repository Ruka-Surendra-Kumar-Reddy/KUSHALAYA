"use client";

import { COMPANY_CIN, COMPANY_GSTIN, LEGAL_ENTITY_NAME, REGISTERED_ADDRESS } from "@/lib/public-brand";

import { MkLink as Link } from "./MkLink";

import {
  BECOME_A_PARTNER_HREF,
  EMAILS,
  mailtoHref,
  FAMILY_PORTAL_LOGIN,
  PARENT_CARE_CHECK_HREF,
  familyPhoneDisplay,
  familyPhoneTelHref,
  familyWhatsAppDigits,
  familyWhatsAppHref,
  US_PHONE,
} from "@/lib/marketing/family-contacts";
import { FOUNDER } from "@/lib/marketing/founder";
import { CALLBACK_PROMISE, SHOW_SUPPORT_HOURS, SUPPORT_HOURS, useSiteConfig, whatsAppHref } from "@/lib/marketing/site-config";
import { EnquiryForm } from "./EnquiryForm";
import { MarketingShell } from "./MarketingShell";
import { ICONS, PageHero, Reveal, SectionHead } from "./ui";

/**
 * Contact page. A business line and WhatsApp number come from
 * NEXT_PUBLIC_FAMILY_PHONE / NEXT_PUBLIC_FAMILY_WHATSAPP when they are set;
 * until then the founder's direct line (public by his own decision, see
 * lib/marketing/founder.ts) is the number shown, so the page is never empty.
 */
export function ContactMarketingPage() {
  const businessPhone = familyPhoneDisplay();
  const phoneLabel = businessPhone || FOUNDER.phoneDisplay;
  const phoneHref = businessPhone ? familyPhoneTelHref() : FOUNDER.phoneTel;
  // Settings → Care team WhatsApp wins; the build-time number only while that is unset.
  const site = useSiteConfig();
  const whatsappHref =
    site.whatsapp_is_default && familyWhatsAppDigits()
      ? familyWhatsAppHref()
      : whatsAppHref(site, "Hi, I have a question about care for my parents.");

  return (
    <MarketingShell>
      <PageHero
        eyebrow="Contact us"
        title="Talk to a real person."
        accent={`${CALLBACK_PROMISE}.`}
        lede="Call, message or write to us about your parents, a plan, or a partnership. Or leave your details and we'll call you back at a time that suits you."
        image="/marketing/contact.webp"
        imageAlt="A care coordinator smiling during a phone call at her desk"
      >
        <a className="mk-btn mk-btn-primary mk-btn-lg" href={phoneHref}>
          {ICONS.phone} Call {phoneLabel}
        </a>
        <a
          className="mk-btn mk-btn-green mk-btn-lg"
          href={whatsappHref}
          target="_blank"
          rel="noopener noreferrer"
        >
          {ICONS.whatsapp} WhatsApp
        </a>
      </PageHero>

      <section className="mk-band" aria-labelledby="contact-form-title">
        <div className="mk-wrap mk-contact-grid">
          <Reveal>
            <SectionHead eyebrow="Reach us" title="Choose what's easiest" />
            <div className="mk-contact-cards">
              <a className="mk-contact-card" href={phoneHref}>
                <span className="mk-card-ico">{ICONS.phone}</span>
                <span>
                  <small>Phone</small>
                  <strong>{phoneLabel}</strong>
                  <em>{businessPhone ? "Care team" : `${FOUNDER.name}, founder — direct line`}</em>
                </span>
              </a>
              <a className="mk-contact-card" href={US_PHONE.tel}>
                <span className="mk-card-ico">{ICONS.phone}</span>
                <span>
                  <small>From the US &amp; Canada</small>
                  <strong>{US_PHONE.display}</strong>
                  <em>Local call for families in North America</em>
                </span>
              </a>
              <a
                className="mk-contact-card"
                href={whatsappHref}
                target="_blank"
                rel="noopener noreferrer"
              >
                <span className="mk-card-ico is-green">{ICONS.whatsapp}</span>
                <span>
                  <small>WhatsApp</small>
                  <strong>Send us a message</strong>
                  <em>Photos and voice notes welcome</em>
                </span>
              </a>
              <a className="mk-contact-card" href={mailtoHref(EMAILS.contact, "Care for my parents")}>
                <span className="mk-card-ico is-gold">{ICONS.mail}</span>
                <span>
                  <small>Email</small>
                  <strong>{EMAILS.contact}</strong>
                  <em>Care, visits, plans or your account: one inbox</em>
                </span>
              </a>
              <a className="mk-contact-card" href={FAMILY_PORTAL_LOGIN}>
                <span className="mk-card-ico">{ICONS.users}</span>
                <span>
                  <small>Already a family?</small>
                  <strong>Sign in to the family portal</strong>
                  <em>Messages go straight to your care manager</em>
                </span>
              </a>
            </div>
            {SHOW_SUPPORT_HOURS ? (
              <p className="mk-contact-hours">
                <strong>Hours:</strong> {SUPPORT_HOURS.ist}
                <span>{SUPPORT_HOURS.us}</span>
                <span>{SUPPORT_HOURS.uk}</span>
              </p>
            ) : null}
            <p className="mk-note" style={{ marginTop: "1rem" }}>
              In an emergency, call your local emergency number first — then us.
            </p>
            <p className="mk-note">
              {LEGAL_ENTITY_NAME} · CIN {COMPANY_CIN} · GSTIN {COMPANY_GSTIN}
              <br />
              Registered office: {REGISTERED_ADDRESS}
            </p>
          </Reveal>

          <Reveal delay={120} className="mk-form-card">
            <p className="mk-eyebrow">Request a call back</p>
            <h2 id="contact-form-title" style={{ fontSize: "1.5rem", marginBottom: "1rem" }}>
              Tell us a little about your parents
            </h2>
            <EnquiryForm kind="contact" submitLabel="Request a call back" />
          </Reveal>
        </div>
      </section>

      <section className="mk-band mk-band-soft" aria-labelledby="contact-more-title">
        <div className="mk-wrap">
          <SectionHead id="contact-more-title" eyebrow="Not sure where to start?" title="Two good first steps" />
          <div className="mk-grid-2">
            <Reveal className="mk-card" as="article">
              <span className="mk-card-ico is-green">{ICONS.clipboard}</span>
              <h3>KushCare Discovery</h3>
              <p>A few questions about your parent, and we tell you whether a full home assessment is worth it.</p>
              <Link className="mk-inline-link" href={PARENT_CARE_CHECK_HREF} style={{ marginTop: "0.75rem" }}>
                Start the check {ICONS.arrow}
              </Link>
            </Reveal>
            <Reveal className="mk-card" as="article" delay={80}>
              <span className="mk-card-ico is-gold">{ICONS.tool}</span>
              <h3>Partners and installers</h3>
              <p>Supply or install safety products, or provide physiotherapy or nursing? Join the Trusted Partner Network.</p>
              <Link className="mk-inline-link" href={BECOME_A_PARTNER_HREF} style={{ marginTop: "0.75rem" }}>
                Become a partner {ICONS.arrow}
              </Link>
            </Reveal>
          </div>
        </div>
      </section>
    </MarketingShell>
  );
}
