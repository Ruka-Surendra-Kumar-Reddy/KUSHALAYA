"use client";

import { useEffect, useState } from "react";

import {
  BILLING_PERIODS,
  PERIOD_LABEL,
  PERIOD_SUFFIX,
  type BillingPeriod,
  formatInr,
  formatUsdApprox,
  priceForPeriod,
} from "@/lib/marketing/pricing";
import { CARE_PLANS, EVERY_PLAN, MONTHLY_NOTE, PLAN_COMPARISON, monthlyLine } from "@/lib/marketing/plans";
import { cycleForPeriod } from "@/lib/marketing/plan-checkout";
import { BuyNowSheet } from "./BuyNowSheet";
import { PayAsYouGo } from "./PayAsYouGo";

const PLAN_PREFS_KEY = "mk-plan-prefs";

/**
 * Care plans from the catalog (lib/care-plan-catalog.ts), led by how often a care
 * manager visits. Yearly is the default; every plan can also be paid monthly,
 * which costs more. What every plan includes is listed once, above the cards.
 */
export function CarePlans({
  ctaHref,
  onRequestCustom,
  headingAs: Heading = "h2",
}: {
  ctaHref: string;
  onRequestCustom?: () => void;
  /** Use "h1" when this section opens the page. */
  headingAs?: "h1" | "h2";
}) {
  const [period, setPeriod] = useState<BillingPeriod>("annual");
  const [usd, setUsd] = useState(false);
  const [buying, setBuying] = useState<string | null>(null);
  const money = (inr: number) => (usd ? formatUsdApprox(inr) : formatInr(inr));

  // Remember the visitor's choice; on a first visit from outside India
  // (browser time zone), start in dollars.
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(PLAN_PREFS_KEY) || "null") as { period?: BillingPeriod; usd?: boolean } | null;
      if (saved && typeof saved.usd === "boolean") {
        setUsd(saved.usd);
        if (saved.period && BILLING_PERIODS.includes(saved.period)) setPeriod(saved.period);
        return;
      }
    } catch {
      /* storage blocked: fall through to the time-zone guess */
    }
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    if (tz && tz !== "Asia/Kolkata" && tz !== "Asia/Calcutta") setUsd(true);
  }, []);

  function choose(next: { period?: BillingPeriod; usd?: boolean }) {
    const p = next.period ?? period;
    const u = next.usd ?? usd;
    setPeriod(p);
    setUsd(u);
    try {
      localStorage.setItem(PLAN_PREFS_KEY, JSON.stringify({ period: p, usd: u }));
    } catch {
      /* not saved: fine */
    }
  }

  return (
    <section className="mk-band mk-band-soft" id="plans" aria-labelledby="mk-plans-title">
      <div className="mk-wrap">
        <header className="mk-section-head">
          <p className="mk-eyebrow">Care plans</p>
          <Heading id="mk-plans-title">Pick how often someone visits</Heading>
          <p className="mk-sub">
            Prices include GST. Pay yearly, or monthly for a little more. Safety products are
            quoted separately.
          </p>
          <p className="mk-sub">{MONTHLY_NOTE}</p>
        </header>

        <div className="mk-plan-switches">
        <div className="mk-period" role="radiogroup" aria-label="Billing period">
          {BILLING_PERIODS.map((p) => (
            <button
              key={p}
              type="button"
              role="radio"
              aria-checked={period === p}
              className={period === p ? "mk-period-btn is-on" : "mk-period-btn"}
              onClick={() => choose({ period: p })}
            >
              {PERIOD_LABEL[p]}
            </button>
          ))}
        </div>
        <div className="mk-currency" role="radiogroup" aria-label="Show prices in">
          <button type="button" role="radio" aria-checked={!usd} className={!usd ? "is-on" : ""} onClick={() => choose({ usd: false })}>
            ₹ INR
          </button>
          <button type="button" role="radio" aria-checked={usd} className={usd ? "is-on" : ""} onClick={() => choose({ usd: true })}>
            $ USD
          </button>
          {usd ? <span className="mk-currency-note">Approximate. All plans are billed in rupees.</span> : null}
        </div>
        </div>

        <div className="mk-card" style={{ marginBottom: "1.5rem" }}>
          <h3>Every annual plan includes</h3>
          <ul className="mk-checklist">
            {EVERY_PLAN.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>

        <ul className="mk-plan-grid">
          {CARE_PLANS.map((plan) => {
            const total = priceForPeriod(plan.id, period);
            return (
              <li
                key={plan.id}
                className={plan.highlight ? "mk-plan is-pick" : "mk-plan"}
              >
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
                  <strong>{total === null ? "On assessment" : money(total)}</strong>
                  {total !== null ? <span>{PERIOD_SUFFIX[period]}</span> : null}
                </p>
                <p className="mk-plan-permonth">
                  {period === "annual"
                    ? `${monthlyLine(plan, money)}${usd && total !== null ? ` · billed ${formatInr(total)}` : ""}`
                    : `${money(plan.annualInr)} a year if paid yearly${usd && total !== null ? ` · billed ${formatInr(total)} a month` : ""}`}
                </p>

                <ul className="mk-plan-list">
                  {plan.includes.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>

                {/* Last, so every card reads price → what you get → buy, and the
                    buttons line up along the bottom of the row. */}
                <div className="mk-plan-ctas">
                  <button type="button" className="mk-btn mk-btn-primary" onClick={() => setBuying(plan.id)}>
                    Buy now
                  </button>
                  <a className="mk-plan-alt" href={ctaHref}>
                    Book free assessment
                  </a>
                </div>
              </li>
            );
          })}
        </ul>

        {buying ? (
          <BuyNowSheet planId={buying} initialCycle={cycleForPeriod(period)} onClose={() => setBuying(null)} />
        ) : null}

        <PayAsYouGo ctaHref={ctaHref} />

        <details className="mk-compare">
          <summary>Compare all plans side by side</summary>
          <p className="mk-compare-hint" aria-hidden="true">
            Swipe to compare →
          </p>
          <div className="mk-compare-scroll">
            <table className="mk-compare-table">
              <caption className="mk-sr">Care plans compared</caption>
              <thead>
                <tr>
                  <th scope="col">&nbsp;</th>
                  {CARE_PLANS.map((p) => (
                    <th scope="col" key={p.id}>
                      {p.shortName}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="mk-compare-price">
                  <th scope="row">Price ({PERIOD_LABEL[period].toLowerCase()})</th>
                  {CARE_PLANS.map((p) => {
                    const total = priceForPeriod(p.id, period);
                    return (
                      <td key={p.id}>
                        {total === null ? "—" : `${money(total)} ${PERIOD_SUFFIX[period]}`}
                      </td>
                    );
                  })}
                </tr>
                {PLAN_COMPARISON.map((row) => (
                  <tr key={row.label}>
                    <th scope="row">{row.label}</th>
                    {CARE_PLANS.map((p) => (
                      <td key={p.id}>{row.value(p)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>

        <p className="mk-plan-foot">
          Need something different — more visits, fewer services, or help only during a
          recovery?{" "}
          {onRequestCustom ? (
            <button type="button" className="mk-inline-link mk-link-btn" onClick={onRequestCustom}>
              Build your own plan
            </button>
          ) : (
            <a className="mk-inline-link" href="#custom-plan">Build your own plan</a>
          )}
        </p>
      </div>
    </section>
  );
}
