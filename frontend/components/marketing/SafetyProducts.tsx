"use client";

import { useState } from "react";

import {
  PRODUCT_ROOMS,
  ROOM_LABEL,
  SAFETY_PRODUCTS,
  type ProductRoom,
} from "@/lib/marketing/products";

/**
 * The products we actually fit.
 *
 * Families arrive not knowing what exists, so each card leads with the photo
 * and what the thing *does*, then says what we check before recommending it —
 * which is the difference between Kushalaya and buying a grab bar online.
 *
 * No prices: the right product depends on the wall, the layout and the user's
 * weight, so everything is quoted after the visit.
 */
export function SafetyProducts({ ctaHref }: { ctaHref: string }) {
  const [room, setRoom] = useState<ProductRoom | "all">("all");
  const shown =
    room === "all" ? SAFETY_PRODUCTS : SAFETY_PRODUCTS.filter((p) => p.room === room);

  return (
    <section className="mk-band" id="products" aria-labelledby="mk-products-title">
      <div className="mk-wrap">
        <header className="mk-section-head">
          <p className="mk-eyebrow">What we fit</p>
          <h2 id="mk-products-title">The products that make a home safer</h2>
          <p className="mk-sub">
            These are the items we most often fit after an assessment. We supply and install
            them, so there is one team accountable for whether it is done properly — not a
            box left at the door.
          </p>
        </header>

        <div className="mk-filter" role="group" aria-label="Filter by room">
          <button
            type="button"
            className={room === "all" ? "mk-filter-btn is-on" : "mk-filter-btn"}
            aria-pressed={room === "all"}
            onClick={() => setRoom("all")}
          >
            All rooms
          </button>
          {PRODUCT_ROOMS.map((r) => (
            <button
              key={r}
              type="button"
              className={room === r ? "mk-filter-btn is-on" : "mk-filter-btn"}
              aria-pressed={room === r}
              onClick={() => setRoom(r)}
            >
              {ROOM_LABEL[r]}
            </button>
          ))}
        </div>

        <ul className="mk-product-grid">
          {shown.map((p) => (
            <li key={p.id} className="mk-product">
              <div className="mk-product-photo">
                {/* eslint-disable-next-line @next/next/no-img-element -- static marketing asset */}
                <img src={p.image} alt={p.name} width={600} height={450} loading="lazy" decoding="async" />
                {p.tag ? <span className="mk-product-tag">{p.tag}</span> : null}
              </div>
              <div className="mk-product-body">
                <p className="mk-product-room">{ROOM_LABEL[p.room]}</p>
                <h3>{p.name}</h3>
                <p className="mk-product-use">{p.use}</p>
                <p className="mk-product-check">
                  <strong>We check:</strong> {p.check}
                </p>
              </div>
            </li>
          ))}
        </ul>

        <div className="mk-products-foot">
          <p className="mk-note">
            Anything fixed to a wall — grab bars and fold-up rails — has to go into solid
            masonry or concrete, not just tile or a partition board. That is one of the first
            things we check on the visit, and it is why we quote after seeing the home rather
            than from a price list.
          </p>
          <a className="mk-btn mk-btn-primary" href={ctaHref}>
            Book an assessment
          </a>
        </div>
      </div>
    </section>
  );
}
