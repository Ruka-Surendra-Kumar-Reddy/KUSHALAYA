"use client";

import { FamilyPhotoImage } from "@/components/livewell/family/FamilyPhotoImage";
import { VisualizationProductsList } from "@/components/livewell/VisualizationProductsList";
import type { FamilyApprovedVisual } from "@/lib/livewell/familyApi";

const TIER_LABELS: Record<string, string> = {
  essential: "Essential",
  comfort: "Comfort",
  premium: "Premium",
};

function productSummary(visual: FamilyApprovedVisual): string {
  const items =
    (visual.product_labels?.length ? visual.product_labels : null) ??
    (visual.product_codes?.length ? visual.product_codes : null) ??
    [];
  if (!items.length) return "";
  return ` Products included: ${items.join(", ")}.`;
}

function tierLabel(level: string | null | undefined): string {
  if (!level) return "";
  return TIER_LABELS[level] || level.replace(/_/g, " ");
}

export function FamilyVisualPair({ visual }: { visual: FamilyApprovedVisual }) {
  const headingId = `family-visual-${visual.id}-title`;
  const productsId = `family-visual-${visual.id}-products`;
  const productsNote = productSummary(visual);
  const tier = tierLabel(visual.package_level);
  const productCount =
    visual.product_labels?.length || visual.product_codes?.length || 0;

  return (
    <article
      className="ai-phase-approved-gallery is-approved home-safety-family-visual-card"
      aria-labelledby={headingId}
    >
      <header className="ai-phase-approved-gallery-head">
        <h3 id={headingId}>Approved after photo</h3>
        <p className="muted">
          {visual.label}
          {tier && !visual.label.toLowerCase().includes(tier.toLowerCase())
            ? ` · ${tier}`
            : ""}
          {productCount
            ? ` · ${productCount} product${productCount === 1 ? "" : "s"} included`
            : " · ready for your plan"}
        </p>
      </header>

      <div
        className="ai-phase-pair home-safety-family-visual-pair"
        role="group"
        aria-label={`Before and after photos for ${visual.label}.${productsNote}`}
      >
        <figure>
          <figcaption>Before</figcaption>
          <FamilyPhotoImage
            url={visual.before_url}
            alt={`Before: ${visual.label} room photo`}
            className="ai-phase-thumb home-safety-family-photo-img"
          />
        </figure>
        <figure>
          <figcaption>After (approved)</figcaption>
          <FamilyPhotoImage
            url={visual.after_url}
            alt={`After: ${visual.label} with proposed safety improvements.${productsNote}`}
            className="ai-phase-thumb home-safety-family-photo-img"
          />
        </figure>
      </div>

      <VisualizationProductsList
        labels={visual.product_labels}
        codes={visual.product_codes}
        heading="Products included"
        headingId={productsId}
        hideWhenEmpty
      />
    </article>
  );
}
