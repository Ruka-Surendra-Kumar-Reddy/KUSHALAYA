"use client";

import { BRAND_ASSETS } from "@/lib/brand-assets";
import { useState } from "react";
import { MkLink as Link } from "./MkLink";

import {
  ABROAD,
  FAQS,
  FINAL_CTA,
  HERO,
  KUSHLIFE_SAMPLE,
  LIVE_STAT_MINIMUM,
  PARTNER_TEASER,
  PROMISES,
  SERVICES,
  STEPS,
  SAMPLE_REPORT,
  WHY,
} from "@/lib/marketing/content";
import {
  BECOME_A_PARTNER_HREF,
  FOUNDER_HREF,
  PACKAGES_HREF,
  PARENT_CARE_CHECK_HREF,
  PARTNERS_HREF,
} from "@/lib/marketing/family-contacts";
import { FOUNDER, KUSHLIFE, founderWhatsAppHref } from "@/lib/marketing/founder";
import { CARE_PLANS, monthlyLine } from "@/lib/marketing/plans";
import { PayAsYouGo } from "./PayAsYouGo";
import { formatInr } from "@/lib/marketing/pricing";
import { publicBrandName, publicSafetyScoreName } from "@/lib/public-brand";
import { MarketingShell } from "./MarketingShell";
import { useSiteConfig, whatsAppHref, type SiteConfig } from "@/lib/marketing/site-config";
import { Counter, ICONS, Photo, Reveal, SectionHead, useLiveStats, type IconName } from "./ui";

const TONES = ["", "is-green", "is-gold"] as const;

/** Sparkline of the sample KushLife trend, drawn when it scrolls into view. */
function TrendChart({ points }: { points: readonly number[] }) {
  const w = 320;
  const h = 72;
  const pad = 6;
  const min = Math.min(...points, 45) - 3;
  const max = Math.max(...points, 55) + 3;
  const x = (i: number) => pad + (i / (points.length - 1)) * (w - pad * 2);
  const y = (v: number) => h - pad - ((v - min) / (max - min)) * (h - pad * 2);
  const line = points.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const area = `${line} L${x(points.length - 1).toFixed(1)},${h} L${x(0).toFixed(1)},${h} Z`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="mk-trend-grad" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#1d5fb4" stopOpacity="0.22" />
          <stop offset="100%" stopColor="#1d5fb4" stopOpacity="0" />
        </linearGradient>
      </defs>
      <line className="mk-trend-base" x1={pad} x2={w - pad} y1={y(50)} y2={y(50)} />
      <path className="mk-trend-fill" d={area} />
      <path className="mk-trend-line" d={line} />
      {points.map((v, i) => (
        <circle
          key={i}
          className="mk-trend-dot"
          cx={x(i)}
          cy={y(v)}
          r={i === points.length - 1 ? 4.5 : 3}
          style={{ ["--i" as string]: i }}
        />
      ))}
    </svg>
  );
}

function PromiseStrip() {
  const live = useLiveStats();
  const showLive = live && live.families >= LIVE_STAT_MINIMUM;
  return (
    <section className="mk-stats" aria-label="What every family gets">
      <div className="mk-wrap">
        <Reveal className="mk-stats-grid">
          {showLive ? (
            <>
              <div className="mk-stat">
                <strong>
                  <Counter value={live.families} suffix="+" />
                </strong>
                <span>Families supported</span>
              </div>
              <div className="mk-stat">
                <strong>
                  <Counter value={live.visits} suffix="+" />
                </strong>
                <span>Care visits completed</span>
              </div>
              <div className="mk-stat">
                <strong>
                  <Counter value={live.assessments} suffix="+" />
                </strong>
                <span>Home assessments</span>
              </div>
              <div className="mk-stat">
                <strong>1 tap</strong>
                <span>SOS watch alerts the care manager</span>
              </div>
            </>
          ) : (
            PROMISES.map((p) => (
              <div key={p.label} className="mk-stat">
                <strong>{p.value}</strong>
                <span>{p.label}</span>
              </div>
            ))
          )}
        </Reveal>
      </div>
    </section>
  );
}

/** Real testimonials from Settings → Website; the section is absent until there is one. */
function Testimonials({ items }: { items: SiteConfig["testimonials"] }) {
  if (!items.length) return null;
  return (
    <>
    <h3 className="mk-testimonials-title" id="testimonials-title">What families say</h3>
    <ul className="mk-testimonials" aria-labelledby="testimonials-title">
      {items.map((t) => (
        <li key={`${t.name}-${t.quote.slice(0, 20)}`}>
          <figure className="mk-testimonial">
            <blockquote>“{t.quote}”</blockquote>
            <figcaption>
              <strong>{t.name}</strong>
              {t.place ? ` · ${t.place}` : ""}
            </figcaption>
          </figure>
        </li>
      ))}
    </ul>
    </>
  );
}

export function FamilyMarketingPage() {
  const [openFaq, setOpenFaq] = useState<number | null>(0);
  const site = useSiteConfig();
  const annualPlans = CARE_PLANS;

  return (
    <MarketingShell>
      {/* Hero */}
      <section className="mk-hero" id="top">
        <div className="mk-wrap mk-hero-grid">
          <Reveal>
            <p className="mk-eyebrow">{HERO.eyebrow}</p>
            <h1>
              {HERO.title}
              <span className="mk-accent">{HERO.accent}</span>
            </h1>
            <p className="mk-lede">{HERO.lede}</p>
            <div className="mk-actions">
              <Link className="mk-btn mk-btn-primary mk-btn-lg" href={PARENT_CARE_CHECK_HREF}>
                {HERO.primary}
                {ICONS.arrow}
              </Link>
              <a
                className="mk-btn mk-btn-green mk-btn-lg"
                href={whatsAppHref(site, "Hi, I'd like to know about care for my parents.")}
                target="_blank"
                rel="noopener noreferrer"
              >
                {ICONS.whatsapp}
                {HERO.secondary}
              </a>
            </div>
            <p className="mk-hero-micro">
              <span className="mk-hero-micro-item">
                KushCare Discovery: <span className="mk-price-chip">{site.assessment_price_label}</span>
              </span>
              {HERO.micro.split(" · ").map((t) => (
                <span key={t} className="mk-hero-micro-item">
                  {t}
                </span>
              ))}
            </p>
          </Reveal>

          <Reveal delay={120} className="mk-hero-stage">
            <Photo
              src="/marketing/hero.webp"
              alt="An elderly couple on their sofa, smiling at a video call with their daughter"
              priority
            />
            <div className="mk-float mk-float-a" aria-hidden="true">
              <span className="mk-float-ico">{ICONS.heart}</span>
              <span className="mk-float-text">
                <small>KushLife check</small>
                <strong>
                  <i className="mk-live" /> All is well today
                </strong>
              </span>
            </div>
            <div className="mk-float mk-float-b" aria-hidden="true">
              <span className="mk-float-ico is-blue">{ICONS.calendar}</span>
              <span className="mk-float-text">
                <small>Next visit</small>
                <strong>Thu · 10:00 AM</strong>
              </span>
            </div>
          </Reveal>
        </div>
      </section>

      <PromiseStrip />

      {/* Why families call us */}
      <section className="mk-band" id="why" aria-labelledby="why-title">
        <div className="mk-wrap mk-two-col">
          <Reveal>
            <p className="mk-eyebrow">{WHY.eyebrow}</p>
            <h2 id="why-title">{WHY.title}</h2>
            {WHY.paras.map((p) => (
              <p key={p} className="mk-sub">
                {p}
              </p>
            ))}
          </Reveal>
          <Reveal delay={120}>
            <Photo src={WHY.image} alt={WHY.imageAlt} />
          </Reveal>
        </div>
      </section>

      {/* How it works */}
      <section className="mk-band mk-band-soft" id="how" aria-labelledby="how-title">
        <div className="mk-wrap">
          <SectionHead
            id="how-title"
            eyebrow="How it works"
            title="Four steps. Always respectful. Always clear."
          />
          <Reveal className="mk-score-callout">
            <strong>{publicSafetyScoreName()}</strong> — every {publicBrandName()} assessment
            produces a scored report <strong>out of 100</strong>. The checklist is informed by
            publicly available AARP and CDC home-safety guidance, plus our own standards for
            Indian homes — so families see a clear mark, not a vague opinion.
          </Reveal>
          <div className="mk-steps">
            {STEPS.map((s) => (
              <Reveal key={s.n} className="mk-step" as="article">
                <div className="mk-step-copy">
                  <span className="mk-step-n">{s.n}</span>
                  <h3>{s.title}</h3>
                  <p className="mk-step-short">{s.short}</p>
                  <p className="mk-step-body">{s.body}</p>
                </div>
                <Photo src={s.image} alt={s.alt} wide />
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* KushLife */}
      <section className="mk-band mk-band-navy mk-on-dark" id="kushlife" aria-labelledby="kushlife-title">
        <div className="mk-wrap mk-kush-grid">
          <Reveal>
            <p className="mk-kush-mark" aria-hidden="true">
              <span className="k">Kush</span>
              <span className="l">Life</span>
            </p>
            <h2 id="kushlife-title">{KUSHLIFE.strap}</h2>
            <p className="mk-lede" style={{ marginTop: "0.9rem" }}>
              {KUSHLIFE.meaning}
            </p>
            <ol className="mk-kush-checks">
              {KUSHLIFE.checks.map((c, i) => (
                <li key={c.title} className="mk-kush-check">
                  <small>{String(i + 1).padStart(2, "0")}</small>
                  <strong>{c.title}</strong>
                  <p>{c.body}</p>
                </li>
              ))}
            </ol>
          </Reveal>

          <Reveal delay={150}>
            <div className="mk-kush-card" aria-label="Example of the KushLife card in the family portal">
              <div className="mk-kush-card-head">
                <span className="mk-avatar">LR</span>
                <span>
                  <strong>
                    Lakshmi Reddy <span className="mk-sample-tag">Sample</span>
                  </strong>
                  <span>{KUSHLIFE_SAMPLE.eyebrow}</span>
                </span>
                <span className="mk-kush-chip">
                  <i className="mk-live" /> All is well
                </span>
              </div>
              <div className="mk-trend">
                <div className="mk-trend-head">
                  <small>KushLife score</small>
                  <strong>
                    {KUSHLIFE_SAMPLE.points[KUSHLIFE_SAMPLE.points.length - 1]}
                    <em>↑ 1 since last visit</em>
                  </strong>
                </div>
                <TrendChart points={KUSHLIFE_SAMPLE.points} />
                <p className="mk-trend-note">{KUSHLIFE_SAMPLE.note}</p>
              </div>
              <ul className="mk-kush-rows">
                {KUSHLIFE_SAMPLE.checks.map((c, i) => (
                  <li key={c.title} style={{ ["--i" as string]: i }}>
                    <span className="mk-tick">{ICONS.check}</span>
                    <strong>{c.title}</strong>
                    <span>{c.note}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Services */}
      <section className="mk-band" id="services" aria-labelledby="services-title">
        <div className="mk-wrap">
          <SectionHead
            id="services-title"
            eyebrow="Services"
            title="Assessment first — then only what the home needs"
            sub="Every service protects independence. All optional, and every home change is quoted as a complete job before work starts."
          />
          <div className="mk-grid-3">
            {SERVICES.map((s, i) => (
              <Reveal key={s.id} className="mk-card" as="article" delay={(i % 3) * 80}>
                <span className={`mk-card-ico ${TONES[i % 3]}`}>{ICONS[s.icon as IconName]}</span>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
                {"link" in s && s.link ? (
                  <Link className="mk-card-link" href={s.link.href}>
                    {s.link.label} {ICONS.arrow}
                  </Link>
                ) : null}
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Plans teaser */}
      <section className="mk-band mk-band-soft" id="plans" aria-labelledby="plans-title">
        <div className="mk-wrap">
          <SectionHead
            id="plans-title"
            eyebrow="Care plans"
            title="Pick how often someone visits"
            sub="Care-manager visits, emergency coordination and family alerts in every plan. Prices include GST; monthly billing available on every plan."
          />
          <ul className="mk-plan-grid">
            {annualPlans.map((plan, i) => (
              <Reveal key={plan.id} as="li" delay={i * 80} className={plan.highlight ? "mk-plan is-pick" : "mk-plan"}>
                {plan.highlight ? <p className="mk-plan-flag">Most popular</p> : null}
                <h3>{plan.name}</h3>
                <p className="mk-plan-fit">{plan.fit}</p>
                <dl className="mk-plan-facts">
                  <div>
                    <dt>Visits</dt>
                    <dd>{plan.visitLabel}</dd>
                  </div>
                  <div>
                    <dt>Billing</dt>
                    <dd>Yearly or monthly</dd>
                  </div>
                </dl>
                <p className="mk-plan-price">
                  <strong>{formatInr(plan.annualInr)}</strong>
                  <span>/ year</span>
                </p>
                <p className="mk-plan-permonth">{monthlyLine(plan)}</p>
                <Link className="mk-btn mk-btn-outline" href={PACKAGES_HREF}>
                  See what&rsquo;s included
                </Link>
              </Reveal>
            ))}
          </ul>
          <PayAsYouGo ctaHref={PARENT_CARE_CHECK_HREF} />
          <p className="mk-plan-foot">
            Need something different?{" "}
            <Link className="mk-inline-link" href={`${PACKAGES_HREF}#custom-plan`}>
              Build your own plan {ICONS.arrow}
            </Link>
          </p>
        </div>
      </section>

      {/* Families abroad */}
      <section className="mk-band" id="abroad" aria-labelledby="abroad-title">
        <div className="mk-wrap mk-two-col">
          <Reveal>
            <Photo src={ABROAD.image} alt={ABROAD.imageAlt} />
          </Reveal>
          <Reveal delay={120}>
            <p className="mk-eyebrow">{ABROAD.eyebrow}</p>
            <h2 id="abroad-title">{ABROAD.title}</h2>
            <p className="mk-sub">{ABROAD.body}</p>
            <ul className="mk-checklist">
              {ABROAD.points.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
            <div className="mk-actions" style={{ marginTop: "1.5rem" }}>
              <Link className="mk-btn mk-btn-primary" href={PARENT_CARE_CHECK_HREF}>
                {site.assessment_is_paid ? "Start with a KushCare Discovery" : "Start with a free KushCare Discovery"}
              </Link>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Sample report + testimonials coming soon */}
      <section className="mk-band mk-band-soft" id="stories" aria-labelledby="stories-title">
        <div className="mk-wrap">
          <SectionHead
            id="stories-title"
            eyebrow="After the assessment"
            title="What you get: a clear, room-by-room report"
            sub={`Every home gets a ${publicSafetyScoreName()}, the risks in each room and the fixes that raise it. Here’s a sample.`}
            center
          />
          <Reveal as="figure" className="mk-report" aria-label="Sample assessment report">
            <div className="mk-report-head">
              <div>
                <small>Home safety report · sample</small>
                <strong>{SAMPLE_REPORT.client}</strong>
              </div>
              <div className="mk-report-score">
                <b>{SAMPLE_REPORT.score}</b>
                <span>/100</span>
                <em>{SAMPLE_REPORT.scoreLabel}</em>
              </div>
            </div>
            <ul className="mk-report-rooms">
              {SAMPLE_REPORT.rooms.map((r) => (
                <li key={r.room}>
                  <span>
                    <strong>{r.room}</strong>
                    <small>{r.note}</small>
                  </span>
                  <i style={{ ["--w" as string]: `${r.score}%` }} aria-hidden="true" />
                  <b>{r.score}</b>
                </li>
              ))}
            </ul>
            <div className="mk-report-fixes">
              <strong>Recommended fixes</strong>
              <ul>
                {SAMPLE_REPORT.fixes.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
              <p>
                Score after fixes: <b>{SAMPLE_REPORT.after}/100</b>
              </p>
            </div>
            <figcaption>Illustrative sample — your report is based on your home.</figcaption>
          </Reveal>
          {site.testimonials.length ? (
            <Testimonials items={site.testimonials} />
          ) : (
            <p className="mk-soon">
              <strong>Family stories, coming soon.</strong> We’re welcoming our first families now — their words will
              live here.
            </p>
          )}
        </div>
      </section>

      {/* Founder teaser */}
      <section className="mk-band mk-founder" id="founder" aria-labelledby="founder-title">
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
              loading="lazy"
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
            <h2 id="founder-title" className="mk-founder-quote">
              {FOUNDER.tagline}
            </h2>
            <p className="mk-founder-para">{FOUNDER.statement[0]}</p>
            <p className="mk-founder-sign">{FOUNDER.name}</p>
            <div className="mk-actions">
              <Link className="mk-btn mk-btn-primary" href={FOUNDER_HREF}>
                Read the founder&rsquo;s note {ICONS.arrow}
              </Link>
              <a className="mk-btn mk-btn-outline" href={FOUNDER.phoneTel}>
                {ICONS.phone} Call {FOUNDER.phoneDisplay}
              </a>
            </div>
          </Reveal>
        </div>
      </section>

      {/* FAQ */}
      <section className="mk-band mk-band-soft" id="faq" aria-labelledby="faq-title">
        <div className="mk-wrap">
          <SectionHead id="faq-title" eyebrow="Questions" title="Questions families ask first" />
          <div className="mk-faq">
            {FAQS.map((item, i) => {
              const open = openFaq === i;
              return (
                <div key={item.q} className={open ? "mk-faq-item is-open" : "mk-faq-item"}>
                  <h3>
                    <button
                      type="button"
                      className="mk-faq-q"
                      aria-expanded={open}
                      onClick={() => setOpenFaq(open ? null : i)}
                    >
                      {item.q}
                      {ICONS.plus}
                    </button>
                  </h3>
                  {open ? <p className="mk-faq-a">{item.a}</p> : null}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Partner teaser */}
      <section className="mk-band" id="partners" aria-labelledby="partners-title">
        <div className="mk-wrap mk-two-col">
          <Reveal>
            <p className="mk-eyebrow">{PARTNER_TEASER.eyebrow}</p>
            <h2 id="partners-title">{PARTNER_TEASER.title}</h2>
            <p className="mk-sub">{PARTNER_TEASER.body}</p>
            <div className="mk-actions" style={{ marginTop: "1.5rem" }}>
              <Link className="mk-btn mk-btn-primary" href={PARTNERS_HREF}>
                Explore the network
              </Link>
              <Link className="mk-btn mk-btn-outline" href={BECOME_A_PARTNER_HREF}>
                Become a partner
              </Link>
            </div>
          </Reveal>
          <Reveal delay={120}>
            <Photo src={PARTNER_TEASER.image} alt={PARTNER_TEASER.imageAlt} />
          </Reveal>
        </div>
      </section>

      {/* Final CTA */}
      <section className="mk-band mk-band-navy mk-on-dark mk-cta" id="contact" aria-labelledby="cta-title">
        <div className="mk-wrap">
          <Reveal className="mk-cta-inner">
            <h2 id="cta-title">{FINAL_CTA.title}</h2>
            <p className="mk-lede">{FINAL_CTA.body}</p>
            <div className="mk-actions">
              <Link className="mk-btn mk-btn-white mk-btn-lg" href={PARENT_CARE_CHECK_HREF}>
                Book an assessment
              </Link>
              <a
                className="mk-btn mk-btn-glass mk-btn-lg"
                href={founderWhatsAppHref()}
                target="_blank"
                rel="noopener noreferrer"
              >
                {ICONS.whatsapp} WhatsApp the founder
              </a>
            </div>
          </Reveal>
        </div>
      </section>
    </MarketingShell>
  );
}
