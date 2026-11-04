"use client";

import { PhoneText } from "./PhoneText";
import { MkLink as Link } from "./MkLink";

import { CONTACT_HREF, FOUNDER_HREF, PARENT_CARE_CHECK_HREF, US_PHONE } from "@/lib/marketing/family-contacts";
import { FOUNDER } from "@/lib/marketing/founder";
import { COMPANY_CIN, COMPANY_GSTIN, COMPANY_INCORPORATED, LEGAL_ENTITY_NAME } from "@/lib/public-brand";
import { CALLBACK_PROMISE, useSiteConfig } from "@/lib/marketing/site-config";
import { MarketingShell } from "./MarketingShell";
import { ICONS, PageHero, Reveal, SectionHead } from "./ui";

/** The team (owner, 11 Oct 2026): only these three are named on the site. */
const TEAM = [
  {
    name: FOUNDER.name,
    role: "Founder",
    body: "Started KushAlaya after seeing how often a fall at home is the first sign that help was needed. Leads the company and talks to families directly.",
    photo: FOUNDER.photo,
    href: FOUNDER_HREF,
  },
  {
    name: "Bharani",
    role: "CTO & Head of Care",
    body: "Leads our technology and our care: the family app and safety report, and the caregivers and KushLife checks on every visit.",
  },
  {
    name: "Surendra",
    role: "Software Developer",
    body: "Builds the family app, the safety report and the tools our care team uses on every visit.",
  },
] as const;

const STEPS = [
  { title: "We look first", body: "A KushCare Discovery visit checks the home room by room and gives you a KushAlaya Safety Score." },
  { title: "We tell you what matters", body: "A clear plan: what is urgent, what can wait, and what each fix costs, before anything is done." },
  { title: "We fix it", body: "Grab bars, rails, lighting and anti-slip work fitted by our partners, checked when done." },
  { title: "We keep visiting", body: "Caregivers visit with a KushLife check every time, and you see how your parents are in the family app." },
] as const;

const VALUES = [
  { icon: "shield", title: "Before, not after", body: "We act before a fall or a crisis, not only once something has gone wrong." },
  { icon: "heart", title: "With your parents, not around them", body: "Visits are arranged with them. They can say no to anything." },
  { icon: "doc", title: "Clear prices", body: "You see the price before we book anything. No surprise bills." },
  { icon: "globe", title: "Close, wherever you live", body: "Updates after every visit, a weekly summary and a monthly letter, in your time zone." },
] as const;

function initials(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export function AboutMarketingPage() {
  const site = useSiteConfig();
  const company = site.company;
  const legalName = company.legal_name || LEGAL_ENTITY_NAME;

  return (
    <MarketingShell>
      <PageHero
        eyebrow="About us"
        title="We help families keep ageing parents safe at home,"
        accent="wherever the family lives."
        lede="KushAlaya works with families across India. We check your parents' home, fix what could cause a fall, and visit regularly, so you always know how they are, even from far away."
        image="/marketing/kushlife-visit.webp"
        imageAlt="A KushAlaya caregiver chatting with an older woman at home"
      >
        <Link className="mk-btn mk-btn-primary mk-btn-lg" href={PARENT_CARE_CHECK_HREF}>
          Start KushCare Discovery {ICONS.arrow}
        </Link>
        <Link className="mk-btn mk-btn-ghost mk-btn-lg" href={CONTACT_HREF}>
          Talk to us
        </Link>
      </PageHero>

      <section className="mk-band" aria-labelledby="about-story-title">
        <div className="mk-wrap mk-about-story">
          <SectionHead id="about-story-title" eyebrow="Why we exist" title="Most falls at home can be prevented" />
          <Reveal>
            <p>
              Many older parents live on their own while their children work in another city or another country.
              The home they have lived in for decades slowly becomes harder to live in: a step without a rail, a
              wet bathroom floor, a dark corridor at night. Often nobody notices until there is a fall.
            </p>
            <p>
              We started KushAlaya to change that. We look at the home with a trained eye, fix the risks, and keep
              visiting, so problems are caught early and families are never left guessing.
            </p>
          </Reveal>
        </div>
      </section>

      <section className="mk-band mk-band-soft" aria-labelledby="about-how-title">
        <div className="mk-wrap">
          <SectionHead id="about-how-title" eyebrow="How we work" title="Four steps, one team" center />
          <div className="mk-grid-4">
            {STEPS.map((s, i) => (
              <Reveal key={s.title} className="mk-card" as="article" delay={i * 80}>
                <span className="mk-step-n">{String(i + 1).padStart(2, "0")}</span>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="mk-band" aria-labelledby="about-team-title">
        <div className="mk-wrap">
          <SectionHead id="about-team-title" eyebrow="Our team" title="The people behind KushAlaya" center />
          <div className="mk-grid-3">
            {TEAM.map((p, i) => (
              <Reveal key={p.name} className="mk-card mk-team-card" as="article" delay={i * 80}>
                {"photo" in p && p.photo ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img className="mk-team-photo" src={p.photo} alt={p.name} width={96} height={96} loading="lazy" />
                ) : (
                  <span className="mk-team-photo mk-team-initials" aria-hidden="true">
                    {initials(p.name)}
                  </span>
                )}
                <h3>{p.name}</h3>
                <p className="mk-team-role">{p.role}</p>
                <p>{p.body}</p>
                {"href" in p && p.href ? (
                  <Link className="mk-team-link" href={p.href}>
                    Read {p.name.split(" ")[0]}&apos;s note {ICONS.arrow}
                  </Link>
                ) : null}
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="mk-band mk-band-soft" aria-labelledby="about-values-title">
        <div className="mk-wrap">
          <SectionHead id="about-values-title" eyebrow="What we believe" title="How we treat your family" center />
          <div className="mk-grid-4">
            {VALUES.map((v, i) => (
              <Reveal key={v.title} className="mk-card" as="article" delay={i * 80}>
                <span className={`mk-card-ico ${i % 3 === 1 ? "is-green" : i % 3 === 2 ? "is-gold" : ""}`}>
                  {ICONS[v.icon]}
                </span>
                <h3>{v.title}</h3>
                <p>{v.body}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section className="mk-band" aria-labelledby="about-company-title">
        <div className="mk-wrap mk-about-company">
          <Reveal>
            <p className="mk-eyebrow">Company</p>
            <h2 id="about-company-title">{legalName}</h2>
            <dl className="mk-about-facts">
              {company.address ? (
                <>
                  <dt>Registered office</dt>
                  <dd>{company.address}</dd>
                </>
              ) : null}
              <dt>CIN</dt>
              <dd>{COMPANY_CIN}</dd>
              <dt>GSTIN</dt>
              <dd>{COMPANY_GSTIN}</dd>
              <dt>Incorporated</dt>
              <dd>{COMPANY_INCORPORATED}</dd>
              {company.gstin ? (
                <>
                  <dt>GSTIN</dt>
                  <dd>{company.gstin}</dd>
                </>
              ) : null}
              <dt>India</dt>
              <dd>
                <a href={`tel:${site.phone_tel}`}><PhoneText value={site.phone} /></a>
              </dd>
              <dt>US &amp; Canada</dt>
              <dd>
                <a href={US_PHONE.tel}>{US_PHONE.display}</a>
              </dd>
            </dl>
            <p className="mk-sub">{CALLBACK_PROMISE}.</p>
          </Reveal>
        </div>
      </section>
    </MarketingShell>
  );
}
