"use client";

/**
 * The one way families see a product or service (Requests, Score & plan, quotes):
 * square picture, name, one plain line, a simple price and a single Request button.
 * Tapping the card opens a detail sheet. Never shows cost or margin — the data has none.
 */
import type { ReactNode } from "react";
import { FamilyConfirmSheet } from "@/components/livewell/family/FamilyConfirmSheet";
import { productImageSrc } from "@/lib/commerce";
import { familyPriceLabel } from "@/lib/family-catalog";
import type { FamilyProduct } from "@/lib/family-money";
import { plainWords } from "@/lib/livewell/familyWords";
import { forSelf, useFamilySelf } from "@/lib/livewell/familySelf";

/** Square, rounded, cover-cropped picture; a soft placeholder when there is none. */
export function FamilyProductThumb({ src, size = 72 }: { src: string | null | undefined; size?: number }) {
  const url = src ? productImageSrc(src) : null;
  return url ? (
    <img className="fh-prod-thumb" src={url} alt="" width={size} height={size} loading="lazy" decoding="async" />
  ) : (
    <span className="fh-prod-thumb fh-prod-thumb-empty" style={{ width: size, height: size }} aria-hidden="true" />
  );
}

export function FamilyProductCard({
  p,
  onOpen,
  onRequest,
  requested = false,
  note,
}: {
  p: FamilyProduct;
  onOpen: (p: FamilyProduct) => void;
  onRequest: (p: FamilyProduct) => void;
  requested?: boolean;
  /** Extra line, e.g. why the assessment suggested it. */
  note?: ReactNode;
}) {
  const self = useFamilySelf();
  return (
    <li className="fh-prod">
      <button type="button" className="fh-prod-open" onClick={() => onOpen(p)} aria-label={`About ${p.name}`}>
        <FamilyProductThumb src={p.image_url} />
        <span className="fh-prod-text">
          <strong className="fh-prod-name">{plainWords(p.name)}</strong>
          {p.description ? <span className="fh-prod-desc">{plainWords(forSelf(p.description, self.elderName, self.isSelf))}</span> : null}
          {note ? <span className="fh-prod-note">{note}</span> : null}
          <span className="fh-prod-price">{familyPriceLabel(p)}</span>
        </span>
      </button>
      {requested ? (
        <span className="fh-prod-done">Requested ✓</span>
      ) : (
        <button type="button" className="fh-prod-req" onClick={() => onRequest(p)} aria-label={`Request ${p.name}`}>
          Request
        </button>
      )}
    </li>
  );
}

/** Bigger picture, what it does, what's included, price, Request. */
export function FamilyProductSheet({
  p,
  onClose,
  onRequest,
  requested = false,
}: {
  p: FamilyProduct | null;
  onClose: () => void;
  onRequest: (p: FamilyProduct) => void;
  requested?: boolean;
}) {
  // "Lets your parent sit…" reads "Lets you sit…" for the elder themself.
  const self = useFamilySelf();
  if (!p) return null;
  return (
    <FamilyConfirmSheet
      open
      title={plainWords(p.name)}
      confirmLabel={requested ? "Requested ✓" : "Request"}
      busy={requested}
      cancelLabel="Close"
      onConfirm={() => onRequest(p)}
      onCancel={onClose}
    >
      <div className="fh-prod-sheet">
        <FamilyProductThumb src={p.image_url} size={240} />
        {p.description ? <p>{plainWords(forSelf(p.description, self.elderName, self.isSelf))}</p> : null}
        <dl className="fh-sheet-rows">
          <div>
            <dt>Price</dt>
            <dd>
              <strong>{familyPriceLabel(p)}</strong>
            </dd>
          </div>
          {p.included ? (
            <div>
              <dt>What&apos;s included</dt>
              <dd>{plainWords(p.included)}</dd>
            </div>
          ) : null}
          <div>
            <dt>Type</dt>
            <dd>{p.kind === "service" ? "Service" : "Product"} · {p.category}</dd>
          </div>
        </dl>
        <p className="muted">Your care team confirms the details and the date. Nothing is charged until you approve.</p>
      </div>
    </FamilyConfirmSheet>
  );
}
