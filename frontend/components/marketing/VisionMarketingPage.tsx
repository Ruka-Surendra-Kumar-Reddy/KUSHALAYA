"use client";

import { PhoneText } from "./PhoneText";
import { MkLink as Link } from "./MkLink";
import { assessmentWording, useSiteConfig } from "@/lib/marketing/site-config";

import { BRAND_ASSETS, BRAND_ASSET_SIZE } from "@/lib/brand-assets";
import {
  BECOME_A_PARTNER_HREF,
  BROCHURE_HREF,
  EMAILS,
  PARTNERS_HREF,
  SAFE_HOMES_HREF,
} from "@/lib/marketing/family-contacts";
import { FOUNDER, KUSHLIFE, founderMailtoHref } from "@/lib/marketing/founder";
import { publicBrandName, withPublicBrand, publicSafetyScoreName } from "@/lib/public-brand";
import { MarketingShell } from "./MarketingShell";

/** QR target. Still drawn by api.qrserver.com — no QR library is installed. */
const PCC_URL = "https://www.kushalaya.com/kushcare-discovery";
const QR_SRC = `https://api.qrserver.com/v1/create-qr-code/?size=240x240&margin=8&color=0e2a4f&data=${encodeURIComponent(PCC_URL)}`;

const WHAT_WE_DO = [
  `Professional home safety assessments (${publicSafetyScoreName()})`,
  "Personalised safety and independence reports",
  "Home modifications and accessibility improvements",
  "Care management, physiotherapy and wellness visits",
  `${KUSHLIFE.name} — a four-point check on every visit`,
  "Family portal updates and coordination",
] as const;

export function VisionMarketingPage() {
  const { isFree } = assessmentWording(useSiteConfig());
  return (
    <MarketingShell>
      <div className="mk-print-toolbar mk-no-print">
        <p>
          Vision sheet — use your browser&rsquo;s <strong>Print</strong> (Ctrl/Cmd+P) and choose
          &ldquo;Save as PDF&rdquo;.
        </p>
        <button type="button" className="mk-btn mk-btn-primary" onClick={() => window.print()}>
          Print / Save PDF
        </button>
      </div>

      <article className="mk-sheet" aria-label={`${publicBrandName()} vision sheet`}>
        <header className="mk-sheet-brand">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={BRAND_ASSETS.header}
            alt=""
            width={BRAND_ASSET_SIZE.header.width}
            height={BRAND_ASSET_SIZE.header.height}
          />
          <span>
            <strong>{publicBrandName()}</strong>
            <br />
            <span className="mk-muted">Vision sheet</span>
          </span>
        </header>

        <h1>Helping seniors stay independent at home</h1>
        <p className="mk-sub">
          Safe homes. Independent lives. Ageing in place with dignity — and peace of mind for
          families.
        </p>

        <h2>Who we are</h2>
        <p>
          {withPublicBrand(
            "LiveWell360 is an ageing-in-place company that helps seniors live safely, comfortably and independently in their own homes, while giving families peace of mind.",
          )}
        </p>

        <h2>What we do</h2>
        <ul>
          {WHAT_WE_DO.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>

        <h2>Why it matters</h2>
        <p>
          Many families live away from their ageing parents. We become their trusted partner on the
          ground — coordinating home safety, ongoing support and practical solutions, and noticing
          small changes before they become emergencies.
        </p>

        <h2>From the founder</h2>
        <div className="mk-sheet-founder">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={FOUNDER.photoSmall} width={96} height={120} alt={FOUNDER.photoAlt} />
          <div>
            <p>
              &ldquo;{FOUNDER.statement[1]} {FOUNDER.tagline}&rdquo; — {FOUNDER.name}, {FOUNDER.role}
            </p>
            <p className="mk-note" style={{ marginTop: "0.4rem" }}>
              Call me directly: <a href={FOUNDER.phoneTel}><PhoneText value={FOUNDER.phoneDisplay} /></a> ·{" "}
              <a href={founderMailtoHref()}>{FOUNDER.email}</a>
            </p>
          </div>
        </div>

        <h2>Looking for partners</h2>
        <p>
          Clinicians, therapists, NGOs, apartment communities, product manufacturers, installers,
          hospitals and CSR organisations — help shape the future of ageing in place in India.
        </p>
        <p className="mk-no-print mk-tap-links" style={{ marginTop: "0.4rem" }}>
          <Link href={PARTNERS_HREF}>Trusted Partner Network</Link> ·{" "}
          <Link href={BECOME_A_PARTNER_HREF}>Become a partner</Link>
        </p>

        <footer className="mk-sheet-foot">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={QR_SRC} width={120} height={120} alt="QR code to the KushCare Discovery" />
          <div>
            <p>
              <strong>{isFree ? "Free KushCare Discovery" : "KushCare Discovery"}</strong>
              <br />
              <span className="mk-break">{PCC_URL.replace("https://", "")}</span>
              <br />
              <span className="mk-break">{EMAILS.contact}</span>
            </p>
            <p style={{ marginTop: "0.5rem" }}>
              Assessments are informed by recognised fall-prevention and home-safety guidance
              (including CDC STEADI and AARP principles). We are not endorsed, certified or
              affiliated with CDC or AARP.
            </p>
          </div>
        </footer>
      </article>

      <p className="mk-note mk-no-print" style={{ textAlign: "center", marginBottom: "2.5rem" }}>
        Also see the <Link href={BROCHURE_HREF}>printable brochure</Link> ·{" "}
        <Link href={SAFE_HOMES_HREF}>Why safe homes matter</Link>
      </p>
    </MarketingShell>
  );
}
