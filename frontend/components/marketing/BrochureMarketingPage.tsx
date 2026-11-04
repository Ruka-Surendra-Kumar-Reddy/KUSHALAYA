"use client";

import { PhoneText } from "./PhoneText";
import { MkLink as Link } from "./MkLink";

import { BRAND_ASSETS, BRAND_ASSET_SIZE } from "@/lib/brand-assets";
import { EMAILS, PARENT_CARE_CHECK_HREF, VISION_HREF } from "@/lib/marketing/family-contacts";
import { FOUNDER, KUSHLIFE } from "@/lib/marketing/founder";
import { publicBrandName, publicSafetyScoreName } from "@/lib/public-brand";
import { assessmentWording, useSiteConfig } from "@/lib/marketing/site-config";
import { MarketingShell } from "./MarketingShell";

/** QR target. Still drawn by api.qrserver.com — no QR library is installed. */
const PCC_URL = "https://www.kushalaya.com/kushcare-discovery";
const QR_SRC = `https://api.qrserver.com/v1/create-qr-code/?size=200x200&margin=8&color=0e2a4f&data=${encodeURIComponent(PCC_URL)}`;

export function BrochureMarketingPage() {
  const { isFree } = assessmentWording(useSiteConfig());
  return (
    <MarketingShell>
      <div className="mk-print-toolbar mk-no-print">
        <p>
          Four-panel brochure — print landscape, or <strong>Print → Save as PDF</strong> for a
          handout.
        </p>
        <button type="button" className="mk-btn mk-btn-primary" onClick={() => window.print()}>
          Print / Save PDF
        </button>
      </div>

      <article className="mk-brochure" aria-label={`${publicBrandName()} brochure`}>
        <div className="mk-brochure-panel is-cover">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={BRAND_ASSETS.header}
            alt={publicBrandName()}
            width={BRAND_ASSET_SIZE.header.width}
            height={BRAND_ASSET_SIZE.header.height}
            style={{ width: 72, height: 72, padding: 4, borderRadius: 14, background: "#fff", marginBottom: "1rem" }}
          />
          <h1 style={{ fontSize: "1.8rem" }}>
            Safe homes.
            <br />
            Independent lives.
          </h1>
          <p style={{ marginTop: "0.75rem", color: "rgba(255,255,255,0.85)" }}>
            Home safety and care at home for older adults — so parents stay home with dignity, and
            families know what to do next.
          </p>
          <div className="mk-qr">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={QR_SRC} alt="QR code to the KushCare Discovery" />
            <p>
              {isFree ? "Start free: " : "Start with: "}
              <strong>KushCare Discovery</strong>
            </p>
          </div>
        </div>

        <div className="mk-brochure-panel">
          <h2>The problem</h2>
          <ul>
            <li>Falls are common among older adults — and most happen at home.</li>
            <li>Families, especially abroad, worry but don&rsquo;t know what to fix first.</li>
            <li>Guesswork isn&rsquo;t a plan. Dignity isn&rsquo;t optional.</li>
          </ul>
          <h2>Recognised principles</h2>
          <p>
            Screen · assess · intervene, as in CDC STEADI, and AARP-style home-safety guidance —
            adapted for Indian homes. Not CDC or AARP endorsed.
          </p>
        </div>

        <div className="mk-brochure-panel">
          <h2>How it works</h2>
          <ol>
            <li>
              <strong>KushCare Discovery</strong> — a short form, then a call back from our team
            </li>
            <li>
              <strong>Home assessment</strong> — the home and the elder together, with a {publicSafetyScoreName()}
            </li>
            <li>
              <strong>Improve &amp; support</strong> — priorities, installs, physiotherapy, SOS
            </li>
          </ol>
          <h2>{KUSHLIFE.name}</h2>
          <p>
            {KUSHLIFE.strap} Four checks on every visit:{" "}
            {KUSHLIFE.checks.map((c) => c.title).join(", ")}.
          </p>
        </div>

        <div className="mk-brochure-panel">
          <h2>Start today</h2>
          <p>Scan the code or visit the KushCare Discovery page. We call you back — no obligation to book.</p>
          <div className="mk-qr">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={QR_SRC} alt="" />
            <p>
              <span className="mk-url"><span>kushalaya.com/</span><wbr /><span>kushcare-discovery</span></span>
              <br />
              <PhoneText value={FOUNDER.phoneDisplay} />
              <br />
              <span className="mk-break">{EMAILS.contact}</span>
            </p>
          </div>
          <p style={{ marginTop: "1rem", fontWeight: 700, color: "var(--mk-navy)" }}>
            Safe homes. Independent lives. Care that protects dignity.
          </p>
        </div>
      </article>

      <p className="mk-note mk-no-print" style={{ textAlign: "center", marginBottom: "2.5rem" }}>
        Also see the <Link href={VISION_HREF}>one-page vision sheet</Link> ·{" "}
        <Link href={PARENT_CARE_CHECK_HREF}>KushCare Discovery</Link>
      </p>
    </MarketingShell>
  );
}
