"use client";

import { MkLink as Link } from "./MkLink";

import { BRAND_ASSETS } from "@/lib/brand-assets";
import {
  BROCHURE_HREF,
  PACKAGES_HREF,
  PARENT_CARE_CHECK_HREF,
  PARTNERS_HREF,
  VISION_HREF,
} from "@/lib/marketing/family-contacts";
import { publicBrandName, withPublicBrand, publicSafetyScoreName } from "@/lib/public-brand";
import { assessmentWording, useSiteConfig } from "@/lib/marketing/site-config";
import { MarketingShell } from "./MarketingShell";
import { BeforeAfter } from "./BeforeAfter";
import { ICONS, PageHero, Photo, Reveal, SectionHead, type IconName } from "./ui";

/** Every figure carries a source and link — recognised guidance, not endorsement. */
const STATS = [
  {
    value: "1 in 4",
    detail: "adults 65+ report a fall each year — the leading cause of injury in older adults.",
    source: "CDC",
    href: "https://www.cdc.gov/falls/data-research/",
  },
  {
    value: "Every 11 sec",
    detail: "an older adult is treated in an emergency department for a fall (US data — the pattern is global).",
    source: "CDC / NCOA",
    href: "https://www.ncoa.org/article/get-the-facts-on-falls-prevention/",
  },
  {
    value: "2nd",
    detail: "leading cause of unintentional injury deaths worldwide — an estimated 684,000 fatal falls each year.",
    source: "WHO",
    href: "https://www.who.int/news-room/fact-sheets/detail/falls",
  },
  {
    value: "Preventable",
    detail: "Falls are not an inevitable part of ageing — home and health factors can be addressed.",
    source: "CDC STEADI",
    href: "https://www.cdc.gov/steadi/",
  },
] as const;

const STEADI = [
  {
    tag: "Screen",
    steadi: "CDC STEADI: identify who is at risk.",
    title: "KushCare Discovery",
    body: "Tell us about your loved one in a short form — even from abroad — and we call you back to see whether a full home assessment is worth booking.",
  },
  {
    tag: "Assess",
    steadi: "CDC STEADI: evaluate specific risk factors.",
    title: withPublicBrand("LiveWell360 home assessment"),
    body: "A respectful visit covering lighting, flooring, bathrooms, stairs, mobility and other recognised fall-risk factors — scored out of 100.",
  },
  {
    tag: "Intervene",
    steadi: "CDC STEADI: act on the risks found.",
    title: "Improve · Support · Review",
    body: "Prioritised home changes, wearable SOS where needed, physiotherapy, a KushLife check every visit, and an annual reassessment.",
  },
] as const;

const SAFER_HOME: { icon: IconName; title: string; body: string }[] = [
  { icon: "star", title: "Better lighting", body: "Bright, even light on stairs, hallways and the path to the bathroom — plus reachable switches and night lights." },
  { icon: "walk", title: "Remove trip hazards", body: "Loose mats, cluttered walkways, trailing wires and uneven thresholds are the falls waiting to happen." },
  { icon: "bath", title: "Grab bars & support", body: "Correctly installed grab bars by the toilet, shower and bed give confidence at the riskiest moments." },
  { icon: "pill", title: "Medicine review", body: "Some medicines affect balance. We encourage a review with the family doctor — we complement clinical care, never replace it." },
  { icon: "heart", title: "Balance & strength", body: "Staying active protects independence. Physiotherapy and a home exercise plan are part of every care plan." },
  { icon: "bell", title: "A way to call for help", body: "Wearable SOS to the family portal, plus immobility warnings when the assessment recommends a care alert kit." },
];

const INDIAN_HOME_CHECKLIST = [
  "Wet bathroom floors",
  "Indian vs western toilet transfers",
  "Marble & granite flooring",
  "Balcony thresholds & steps",
  "Water storage / bucket areas",
  "Pooja room steps",
  "Footwear left near entrances",
  "Inverter & generator wiring",
  "Dim apartment corridors",
  "High or low switchboards",
] as const;

const TRUST_SEAL = [
  "Assessment completed",
  "Recommended improvements implemented",
  `${publicSafetyScoreName()} recorded`,
  "Annual review scheduled",
] as const;

const AI_STEPS = [
  { title: "Send a photo. ", body: "Take a picture of the bathroom, bedroom or stairs on your phone." },
  {
    title: "AI checks for risks. ",
    body: "It looks for common hazards such as no grab bar, a slippery floor or a loose rug. Your care manager reviews every finding before you see it.",
  },
  { title: "See the room made safer. ", body: "A preview of the room with the recommended products fitted, with prices from our list." },
] as const;

export function SafeHomesMarketingPage() {
  const { isFree } = assessmentWording(useSiteConfig());
  const ctaLabel = isFree ? "Book a free KushCare Discovery" : "Book a KushCare Discovery";
  return (
    <MarketingShell>
      <PageHero
        eyebrow="Safe homes. Independent lives."
        title="Falls are common."
        accent="They are also largely preventable."
        lede={withPublicBrand(
          "We use internationally recognised fall-prevention principles — like the CDC’s STEADI framework and AARP home-safety guidance — and tailor them for Indian homes. LiveWell360 is the team that turns that guidance into action in your parents’ home.",
        )}
        image="/marketing/safe-homes-hero.webp"
        imageAlt="An elderly woman steadying herself on a bathroom grab bar with a care manager close by"
      >
        <Link className="mk-btn mk-btn-primary mk-btn-lg" href={PARENT_CARE_CHECK_HREF}>
          {ctaLabel}
        </Link>
        <Link className="mk-btn mk-btn-outline mk-btn-lg" href="/#how">
          See how it works
        </Link>
      </PageHero>

      <section className="mk-band mk-band-soft" id="ai" aria-labelledby="assessment-title">
        <div className="mk-wrap mk-assess-basis">
          <Reveal>
            <p className="mk-eyebrow">The KushAlaya Assessment</p>
            <h2 id="assessment-title">Built on fall-prevention science</h2>
            <p className="mk-sub">
              The KushAlaya Assessment is built on respected fall-prevention science, adapted for Indian homes. We start
              with guidance from <strong>AARP HomeFit</strong> and the <strong>CDC STEADI</strong> framework (STEADI
              stands for Stopping Elderly Accidents, Deaths &amp; Injuries), covering the home, movement and daily
              routines that most affect fall risk.
            </p>
            <p className="mk-sub">
              We add proprietary KushAlaya checks of our own, for Indian bathrooms, kitchens, stairs, lighting and the way
              an elder actually lives in their home. Together, these questions produce a{" "}
              <strong>KushAlaya Safety Score</strong> and a prioritised report that shows a family exactly what to fix
              first, rather than a long, unordered list.
            </p>
            <p className="mk-note">This is a home-and-elder safety assessment, not a medical diagnosis.</p>
          </Reveal>
        </div>
        <div className="mk-wrap mk-two-col mk-ai">
          <Reveal>
            <p className="mk-eyebrow">AI room check &amp; preview</p>
            <h3 id="ai-title" className="mk-h2-like">See it before we fit it</h3>
            <p className="mk-sub">
              Send a photo of any room. Our AI points out common risks, and shows the room with the safety products
              already fitted, so you can decide with confidence, even from far away.
            </p>
            <ol className="mk-ai-steps">
              {AI_STEPS.map((s, i) => (
                <li key={s.title}>
                  <span className="mk-step-n">{i + 1}</span>
                  <span>
                    <strong>{s.title}</strong>
                    {s.body}
                  </span>
                </li>
              ))}
            </ol>
            <p className="mk-note">
              Pictures are illustrations: your care manager confirms the final products and where they go. Photos are
              used only for your home&apos;s plan and are never shared or sold.
            </p>
          </Reveal>
          <Reveal delay={120}>
            <BeforeAfter
              before="/marketing/ai/bathroom-before.webp"
              after="/marketing/ai/bathroom-after.webp"
              beforeAlt="A bathroom with no grab bars, a loose mat and a wet floor"
              afterAlt="The same bathroom shown with a fold-up rail by the toilet and grab bars by the shower"
              width={1200}
              height={900}
            />
            <p className="mk-ai-caption">Slide to compare. Grab bars and a fold-up toilet rail, added by our AI preview.</p>
            <p style={{ marginTop: "1rem" }}>
              <Link className="mk-btn mk-btn-primary" href={PARENT_CARE_CHECK_HREF}>
                {ctaLabel}
              </Link>
            </p>
          </Reveal>
        </div>
      </section>

      <section className="mk-band" aria-labelledby="stats-title">
        <div className="mk-wrap">
          <SectionHead
            id="stats-title"
            eyebrow="Why it matters"
            title="The evidence on falls is clear"
            sub="These figures come from recognised public-health sources. They describe the global pattern — our job is to reduce that risk in one specific home: your parents’."
          />
          <div className="mk-evidence">
            {STATS.map((s, i) => (
              <Reveal key={s.value} className="mk-card mk-evidence-card" as="article" delay={i * 70}>
                <strong>{s.value}</strong>
                <p>{s.detail}</p>
                <a href={s.href} target="_blank" rel="noopener noreferrer">
                  Source: {s.source} ↗
                </a>
              </Reveal>
            ))}
          </div>
          <p className="mk-note" style={{ marginTop: "1rem" }}>
            {publicBrandName()} references CDC and AARP guidance for education. We are not endorsed,
            certified or affiliated with either organisation.
          </p>
        </div>
      </section>

      <section className="mk-band mk-band-soft" aria-labelledby="steadi-title">
        <div className="mk-wrap">
          <SectionHead
            id="steadi-title"
            eyebrow="Screen · Assess · Intervene"
            title="Recognised principles, delivered at home"
            sub={withPublicBrand("The CDC’s STEADI programme is built on three ideas. That maps almost exactly to how LiveWell360 works.")}
          />
          <div className="mk-steps-3">
            {STEADI.map((s, i) => (
              <Reveal key={s.tag} className="mk-step-card" as="article" delay={i * 90}>
                <span className="mk-step-n">{String(i + 1).padStart(2, "0")}</span>
                <small>{s.tag}</small>
                <h3>{s.tag === "Screen" && isFree ? `Free ${s.title}` : s.title}</h3>
                <p>{s.body}</p>
                <p className="mk-note" style={{ marginTop: "0.6rem" }}>
                  {s.steadi}
                </p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="mk-band" aria-labelledby="safer-title">
        <div className="mk-wrap">
          <SectionHead
            id="safer-title"
            eyebrow="A practical guide"
            title="What makes a home safer"
            sub="These themes are consistent with recognised fall-prevention guidance — and they are where we focus first."
          />
          <div className="mk-grid-3">
            {SAFER_HOME.map((item, i) => (
              <Reveal key={item.title} className="mk-card" as="article" delay={(i % 3) * 80}>
                <span className={`mk-card-ico ${i % 3 === 1 ? "is-green" : i % 3 === 2 ? "is-gold" : ""}`}>
                  {ICONS[item.icon]}
                </span>
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="mk-band mk-band-soft" aria-labelledby="checklist-title">
        <div className="mk-wrap mk-two-col">
          <Reveal>
            <p className="mk-eyebrow">Built for Indian homes</p>
            <h2 id="checklist-title">A checklist for the way Indian homes are really lived in</h2>
            <p className="mk-sub">
              International guides are written for Western homes. Ours covers what they miss — so
              nothing that matters gets overlooked.
            </p>
            <ul className="mk-chips">
              {INDIAN_HOME_CHECKLIST.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </Reveal>
          <Reveal delay={120}>
            <Photo
              src="/marketing/why-families.webp"
              alt="An elderly man holding the wall for balance near a step in a dim hallway"
            />
          </Reveal>
        </div>
      </section>

      <section className="mk-band" aria-labelledby="seal-title">
        <div className="mk-wrap mk-two-col">
          <Reveal>
            <p className="mk-eyebrow">{withPublicBrand("LiveWell360 Trust Seal")}</p>
            <h2 id="seal-title">Home Safety Certified — by our process</h2>
            <p className="mk-sub">
              When the recommended improvements are done, the home receives our Home Safety
              Certified seal, reviewed every year.
            </p>
            <ul className="mk-checklist">
              {TRUST_SEAL.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
            <p className="mk-note" style={{ marginTop: "1rem" }}>
              The seal is our own certification. It is not a CDC or AARP endorsement.
            </p>
          </Reveal>
          <Reveal delay={120}>
            <div className="mk-seal" aria-label="Home Safety Certified seal">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={BRAND_ASSETS.header} alt="" width={64} height={64} />
              <strong>Home Safety Certified</strong>
              <span>{publicBrandName()} · Annual review</span>
            </div>
          </Reveal>
        </div>
      </section>

      <section className="mk-band mk-band-navy mk-on-dark mk-cta" aria-labelledby="safe-cta-title">
        <div className="mk-wrap">
          <Reveal className="mk-cta-inner">
            <h2 id="safe-cta-title">One simple path to a safer home</h2>
            <p className="mk-lede">
              From a first call to a safer home and ongoing support — with a clear report and a
              written quote at every step.
            </p>
            <div className="mk-actions">
              <Link className="mk-btn mk-btn-white mk-btn-lg" href={PARENT_CARE_CHECK_HREF}>
                {ctaLabel}
              </Link>
              <Link className="mk-btn mk-btn-glass mk-btn-lg" href={PACKAGES_HREF}>
                See plans &amp; products
              </Link>
            </div>
            <p className="mk-note" style={{ color: "rgba(255,255,255,0.75)" }}>
              Printables: <Link href={VISION_HREF} style={{ color: "#fff" }}>Vision sheet</Link> ·{" "}
              <Link href={BROCHURE_HREF} style={{ color: "#fff" }}>Brochure</Link> · For doctors and
              physiotherapists: <Link href={PARTNERS_HREF} style={{ color: "#fff" }}>partner with us</Link>
            </p>
          </Reveal>
        </div>
      </section>
    </MarketingShell>
  );
}
