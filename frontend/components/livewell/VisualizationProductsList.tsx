"use client";

import { useState, type ReactNode } from "react";

/** Shared list of catalog products shown in an AI after-photo concept. */
export function VisualizationProductsList({
  labels,
  codes,
  emptyLabel = "No catalog products recorded for this concept.",
  heading = "Products in after photo",
  headingId,
  hideWhenEmpty = false,
  /** Wrap the list in a collapsible accordion (assessor + family). */
  accordion = true,
  defaultOpen = false,
}: {
  labels?: string[] | null;
  codes?: string[] | null;
  emptyLabel?: string;
  /** Visible section title. */
  heading?: string;
  /** Optional id for aria-labelledby from a parent region. */
  headingId?: string;
  /** When true, render nothing if there are no products (family surfaces). */
  hideWhenEmpty?: boolean;
  accordion?: boolean;
  defaultOpen?: boolean;
}) {
  const items =
    (labels?.length ? labels : null) ??
    (codes?.length ? codes : null) ??
    [];
  const titleId = headingId ?? "viz-products-heading";

  if (!items.length) {
    if (hideWhenEmpty) return null;
    return (
      <p className="muted home-safety-viz-products-empty" role="status">
        {emptyLabel}
      </p>
    );
  }

  const list = (
    <ul className="home-safety-viz-products-list">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );

  if (!accordion) {
    return (
      <div className="home-safety-viz-products" role="region" aria-labelledby={titleId}>
        <h4 id={titleId} className="home-safety-viz-products-heading">
          {heading}
        </h4>
        {list}
      </div>
    );
  }

  return (
    <ProductsAccordion
      titleId={titleId}
      heading={heading}
      itemCount={items.length}
      defaultOpen={defaultOpen}
    >
      {list}
    </ProductsAccordion>
  );
}

function ProductsAccordion({
  titleId,
  heading,
  itemCount,
  defaultOpen,
  children,
}: {
  titleId: string;
  heading: string;
  itemCount: number;
  defaultOpen: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <details
      className="home-safety-viz-products home-safety-viz-products-accordion"
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary id={titleId} className="home-safety-viz-products-summary">
        <span className="home-safety-viz-products-heading">{heading}</span>
        <span className="home-safety-viz-products-count muted">
          {itemCount} item{itemCount === 1 ? "" : "s"}
        </span>
      </summary>
      <div className="home-safety-viz-products-body">{children}</div>
    </details>
  );
}
