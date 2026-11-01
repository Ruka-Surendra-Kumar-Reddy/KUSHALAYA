"use client";

import { useState } from "react";

import { VISIT_PLAN_ID, type VisitNeed } from "@/lib/marketing/plan-checkout";
import { PAY_AS_YOU_GO } from "@/lib/marketing/plans";
import { BuyNowSheet } from "./BuyNowSheet";
import { ICONS } from "./ui";

const POINT_ICONS = [ICONS.shield, ICONS.calendar, ICONS.heart];

/**
 * "Pay as you go" — care without a subscription. It gets its
 * own navy feature card under the plan cards (home page and Packages).
 * "Buy now" (or tapping a list item) pays for one Single priority visit online.
 */
export function PayAsYouGo({ ctaHref }: { ctaHref: string }) {
  // null: closed; "": open with no need picked yet.
  const [buying, setBuying] = useState<VisitNeed | "" | null>(null);
  return (
    <section className="mk-payg" id="pay-as-you-go" aria-labelledby="payg-title">
      <div className="mk-payg-main">
        <span className="mk-payg-tag">{PAY_AS_YOU_GO.eyebrow}</span>
        <h3 id="payg-title">{PAY_AS_YOU_GO.title}</h3>
        <p className="mk-payg-lede">{PAY_AS_YOU_GO.body}</p>
        <ul className="mk-payg-points">
          {PAY_AS_YOU_GO.points.map((pt, i) => (
            <li key={pt.title}>
              <span className="mk-payg-ico" aria-hidden="true">
                {POINT_ICONS[i]}
              </span>
              <span>
                <strong>{pt.title}</strong>
                <small>{pt.note}</small>
              </span>
            </li>
          ))}
        </ul>
      </div>
      <div className="mk-payg-panel">
        <p className="mk-payg-panel-title">Book only what you need</p>
        <ul className="mk-payg-list">
          {PAY_AS_YOU_GO.items.map((it, i) => (
            <li key={it}>
              <button type="button" className="mk-payg-item" onClick={() => setBuying(PAY_AS_YOU_GO.itemNeeds[i] ?? "")}>
                <span aria-hidden="true">{ICONS.check}</span>
                {it}
              </button>
            </li>
          ))}
        </ul>
        <button type="button" className="mk-btn mk-btn-primary mk-payg-btn" onClick={() => setBuying("")}>
          {PAY_AS_YOU_GO.buyCta}
        </button>
        <a className="mk-payg-alt" href={ctaHref}>
          {PAY_AS_YOU_GO.cta}
        </a>
      </div>
      {buying !== null ? (
        <BuyNowSheet planId={VISIT_PLAN_ID} initialCycle="once" initialNeed={buying} onClose={() => setBuying(null)} />
      ) : null}
    </section>
  );
}
