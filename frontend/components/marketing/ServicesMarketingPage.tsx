"use client";

import { MkLink as Link } from "./MkLink";

import { PACKAGES_HREF, PARENT_CARE_CHECK_HREF } from "@/lib/marketing/family-contacts";
import { withPublicBrand } from "@/lib/public-brand";
import { MarketingShell } from "./MarketingShell";
import { ICONS, PageHero, Reveal, SectionHead, type IconName } from "./ui";

type Service = { icon: IconName; title: string; items: string[] };

/** Done by the family's own KushAlaya Family Partner. */
const BY_PARTNER: Service[] = [
  { icon: "shield", title: "Safety", items: ["Emergency response", "Fall prevention", "Home safety checks", "SOS", "Hospital support"] },
  { icon: "heart", title: "Health monitoring", items: ["Regular health checks", "Medicine routine", "Doctor visit follow-up"] },
  { icon: "clipboard", title: "Daily life", items: ["Groceries", "Bills", "Banking", "Pension", "Documentation"] },
  { icon: "chat", title: "Companionship", items: ["Care friend", "Walks", "Games", "Hobbies", "Conversations", "Events"] },
  { icon: "users", title: "Family connect", items: ["Family dashboard", "Updates", "Medical records", "Alerts", "KushLife report"] },
  { icon: "star", title: "Senior life", items: ["Birthday celebrations", "Community events", "Outings"] },
];

/** Delivered by verified partners; the Family Partner arranges and follows up. */
const THROUGH_PARTNERS: Service[] = [
  { icon: "pill", title: "Health at home", items: ["Nurse", "Physiotherapy", "Diagnostics", "Medicine delivery"] },
  { icon: "walk", title: "Caregivers and help", items: ["Caregivers", "Attendants", "Domestic help"] },
  { icon: "tool", title: "Home and property", items: ["Repairs", "Maintenance", "Cleaning", "Security", "Property upkeep"] },
  { icon: "pin", title: "Mobility", items: ["Hospital transport", "Airport", "Shopping", "Religious visits", "Travel", "Pilgrimage"] },
];

function Tiles({ list }: { list: Service[] }) {
  return (
    <div className="mk-grid-3 sv-grid">
      {list.map((s, i) => (
        <Reveal key={s.title} className="mk-card" as="article" delay={i * 60}>
          <span className={`mk-card-ico ${i % 2 ? "is-green" : ""}`}>{ICONS[s.icon]}</span>
          <h3>{s.title}</h3>
          <ul className="mk-chips">
            {s.items.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ul>
        </Reveal>
      ))}
    </div>
  );
}

/** /services: what the KushAlaya Family Partner does, and what comes through partners. */
export function ServicesMarketingPage() {
  return (
    <MarketingShell>
      <PageHero
        eyebrow={withPublicBrand("LiveWell360 Family Partner")}
        title="Your parent’s life, "
        accent="managed with care."
        lede={withPublicBrand(
          "Every family gets one LiveWell360 Family Partner: one person who plans, arranges and checks everything your parent needs at home.",
        )}
      >
        <Link className="mk-btn mk-btn-primary mk-btn-lg" href={PARENT_CARE_CHECK_HREF}>
          Book a free KushCare Discovery
        </Link>
        <Link className="mk-btn mk-btn-ghost mk-btn-lg" href={PACKAGES_HREF}>
          See plans
        </Link>
      </PageHero>

      <section className="mk-band" aria-labelledby="sv-own-title">
        <div className="mk-wrap">
          <SectionHead
            id="sv-own-title"
            eyebrow="By your Family Partner"
            title="What your Family Partner does"
            sub="Done by our own team, on every plan."
          />
          <Tiles list={BY_PARTNER} />
        </div>
      </section>

      <section className="mk-band mk-band-soft" aria-labelledby="sv-partner-title">
        <div className="mk-wrap">
          <SectionHead
            id="sv-partner-title"
            eyebrow="Through trusted partners"
            title="What we arrange through partners"
            sub="Verified partners do the work. Your Family Partner books it and follows up until it is done."
          />
          <Tiles list={THROUGH_PARTNERS} />
        </div>
      </section>

      <section className="mk-band mk-band-navy mk-on-dark mk-cta" aria-labelledby="sv-cta-title">
        <div className="mk-wrap">
          <Reveal className="mk-cta-inner">
            <h2 id="sv-cta-title">Safe, comfortable, dignified. At home.</h2>
            <p className="mk-lede">Start with a free home visit. We listen first, then suggest what fits.</p>
            <div className="mk-actions">
              <Link className="mk-btn mk-btn-white mk-btn-lg" href={PARENT_CARE_CHECK_HREF}>
                Book a free KushCare Discovery
              </Link>
              <Link className="mk-btn mk-btn-glass mk-btn-lg" href={PACKAGES_HREF}>
                See plans
              </Link>
            </div>
          </Reveal>
        </div>
      </section>
    </MarketingShell>
  );
}
