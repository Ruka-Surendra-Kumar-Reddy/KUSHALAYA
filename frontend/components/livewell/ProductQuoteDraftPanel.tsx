"use client";

import Link from "next/link";
import { canOpen } from "@/lib/roles";
import { useEffect, useMemo, useRef, useState } from "react";
import type {
  AssessmentCategory,
  AssessmentQuoteCustomization,
  HomeSafetyAssessment,
} from "@/lib/livewell/assessment";
import { assessmentJobCity } from "@/lib/livewell/assessment";
import { formatInr, productsForPackage } from "@/lib/livewell/catalog";
import type { SafetyCatalog } from "@/lib/livewell/catalog-types";
import { buildImprovementPlan } from "@/lib/livewell/improvement-plan";
import { buildSafeHomeQuote } from "@/lib/livewell/pricing-engine";
import type { QuoteInputs, SafeHomePricingConfig } from "@/lib/livewell/pricing-types";
import { buildQuoteReportText } from "@/lib/livewell/quote-report";
import {
  buildProductRecommendations,
  draftFromQuoteLines,
  hydrateQuoteLineEdits,
  quoteLinesFromRecommended,
  recommendationFromProduct,
  recommendedProductIdsKey,
  serializeQuoteLineEdits,
  type ProductQuoteDraft,
  type QuoteLineEdit,
} from "@/lib/livewell/product-recommendations";
import {
  buildPackageCostComparisons,
  packagesForAssessorQuote,
  type PackageCostComparison,
} from "@/lib/livewell/package-savings";
import {
  ACTIVE_TIERS,
  TIER_LABELS,
  scopeQuoteToPackageTiers,
} from "@/lib/livewell/package-tiers";
import { selectVendorOffer, supplierCostBasisInr } from "@/lib/livewell/supplier-selection";
import type { SupplierDirectory } from "@/lib/livewell/supplier-types";
import type { SolutionLibrary } from "@/lib/livewell/solution-types";
import { withPublicBrand } from "@/lib/public-brand";
import { catalogProductImageSrc } from "@/lib/livewell/catalogImages";

function PackageContentsModal({
  row,
  catalog,
  onClose,
}: {
  row: PackageCostComparison;
  catalog: SafetyCatalog;
  onClose: () => void;
}) {
  const products = productsForPackage(catalog, row.package);
  const overlap = new Set(row.overlapProductIds);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  return (
    <div
      className="home-safety-showcase-modal-backdrop"
      role="presentation"
      onClick={onClose}
    >
      <div
        className="home-safety-showcase-modal card home-safety-package-contents-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="package-contents-title"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          className="home-safety-showcase-modal-close"
          onClick={onClose}
          aria-label="Close"
        >
          ×
        </button>
        <p className="muted" style={{ margin: "0 0 0.25rem", fontSize: "0.8rem" }}>
          Package contents
        </p>
        <h3 id="package-contents-title" style={{ marginTop: 0 }}>
          {row.package.name}
        </h3>
        {row.package.tagline ? (
          <p className="muted" style={{ marginTop: 0 }}>
            {row.package.tagline}
          </p>
        ) : null}
        <p style={{ margin: "0.35rem 0 0.85rem" }}>
          <strong>{formatInr(row.packagePriceInr, "")}</strong>
          <span className="muted"> · {products.length} included product{products.length === 1 ? "" : "s"}</span>
        </p>
        {products.length === 0 ? (
          <p className="muted">No products linked on this package yet.</p>
        ) : (
          <ul className="home-safety-package-contents-list">
            {products.map((prod) => {
              const inQuote = overlap.has(prod.id);
              const src = catalogProductImageSrc(prod);
              const unit = prod.price_inr;
              return (
                <li key={prod.id} className="home-safety-package-contents-row">
                  <div className="home-safety-package-contents-photo" aria-hidden>
                    {src ? (
                      // eslint-disable-next-line @next/next/no-img-element -- catalog URLs
                      <img src={src} alt="" loading="lazy" />
                    ) : (
                      <span>—</span>
                    )}
                  </div>
                  <div className="home-safety-package-contents-copy">
                    <div className="home-safety-package-contents-title-row">
                      <strong>{prod.name}</strong>
                      {inQuote ? (
                        <span className="home-safety-package-contents-badge is-overlap">
                          In quote
                        </span>
                      ) : (
                        <span className="home-safety-package-contents-badge">Also included</span>
                      )}
                    </div>
                    {prod.product_code ? (
                      <span className="muted" style={{ fontSize: "0.8rem" }}>
                        {prod.product_code}
                      </span>
                    ) : null}
                    {prod.short_description ? (
                      <p className="muted" style={{ margin: "0.2rem 0 0", fontSize: "0.85rem" }}>
                        {prod.short_description}
                      </p>
                    ) : null}
                    <p style={{ margin: "0.25rem 0 0", fontSize: "0.85rem" }}>
                      {formatInr(unit, prod.price_label)}
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        <div className="home-safety-package-contents-actions">
          <button type="button" className="secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

function clampMargin(value: number, pricing: SafeHomePricingConfig): number {
  return Math.min(
    pricing.max_margin_percent,
    Math.max(pricing.min_margin_percent, value),
  );
}

export function ProductQuoteDraftPanel({
  assessment,
  categories,
  library,
  catalog,
  pricing,
  suppliers,
  selectedPackageTiers,
  onPackageTiersChange,
  onWorkingDraftChange,
  onQuoteCustomizationChange,
  onQuoteAction,
}: {
  assessment: HomeSafetyAssessment;
  categories: AssessmentCategory[];
  library: SolutionLibrary;
  catalog: SafetyCatalog;
  pricing: SafeHomePricingConfig;
  suppliers?: SupplierDirectory;
  selectedPackageTiers: string[];
  onPackageTiersChange: (tiers: string[]) => void;
  onWorkingDraftChange?: (draft: ProductQuoteDraft) => void;
  onQuoteCustomizationChange?: (custom: AssessmentQuoteCustomization) => void;
  onQuoteAction?: (message: string, error?: string) => void;
}) {
  const fullPlan = useMemo(
    () => buildImprovementPlan(assessment, categories, library),
    [assessment, categories, library],
  );
  const fullDraft = useMemo(
    () => buildProductRecommendations(fullPlan, catalog),
    [fullPlan, catalog],
  );
  const scoped = useMemo(
    () => scopeQuoteToPackageTiers(fullPlan, fullDraft, selectedPackageTiers),
    [fullPlan, fullDraft, selectedPackageTiers],
  );
  const plan = scoped.plan;
  const recommended = scoped.draft;
  const recommendedKey = recommendedProductIdsKey(recommended);

  const custom = assessment.quoteCustomization;
  const [lineEdits, setLineEdits] = useState<QuoteLineEdit[] | null>(null);
  const [addProductId, setAddProductId] = useState("");
  const [openPackageId, setOpenPackageId] = useState<string | null>(null);
  const [inputs, setInputs] = useState<QuoteInputs>(() => ({
    travel_km: custom?.quoteInputs?.travel_km ?? pricing.default_travel_km,
    apply_weekend_surcharge: custom?.quoteInputs?.apply_weekend_surcharge ?? false,
    apply_emergency_surcharge: custom?.quoteInputs?.apply_emergency_surcharge ?? false,
    margin_percent_override:
      custom?.quoteInputs?.margin_percent_override ?? pricing.default_margin_percent,
  }));
  const quoteResetKeyRef = useRef<string | null>(null);

  useEffect(() => {
    const resetKey = `${recommendedKey}::${selectedPackageTiers.join("|")}`;
    const saved = assessment.quoteCustomization;
    const linesStillValid =
      Boolean(saved?.lines?.length) && saved?.recommendedProductKey === recommendedKey;

    if (quoteResetKeyRef.current === null) {
      quoteResetKeyRef.current = resetKey;
      if (linesStillValid && saved?.lines?.length) {
        setLineEdits(hydrateQuoteLineEdits(saved.lines, recommended, catalog));
      } else if (saved?.lines?.length && !linesStillValid) {
        // Ratings/solutions changed since the quote was customized — recalculate.
        setLineEdits(null);
        onQuoteCustomizationChange?.({
          packageTiers: selectedPackageTiers,
          lines: null,
          recommendedProductKey: recommendedKey,
          quoteInputs: saved.quoteInputs,
        });
      }
      return;
    }
    if (quoteResetKeyRef.current !== resetKey) {
      quoteResetKeyRef.current = resetKey;
      setLineEdits(null);
      onQuoteCustomizationChange?.({
        packageTiers: selectedPackageTiers,
        lines: null,
        recommendedProductKey: recommendedKey,
        quoteInputs: {
          travel_km: inputs.travel_km,
          apply_weekend_surcharge: inputs.apply_weekend_surcharge,
          apply_emergency_surcharge: inputs.apply_emergency_surcharge,
          margin_percent_override: inputs.margin_percent_override,
        },
      });
    }
    // Recalculate when recommended products or tiers change; inputs read from latest render.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional
  }, [recommendedKey, selectedPackageTiers, recommended, catalog]);

  const lines = lineEdits ?? quoteLinesFromRecommended(recommended);
  const isCustomized = lineEdits != null;
  const draft = useMemo(
    () => draftFromQuoteLines(lines, recommended.unmappedSolutions),
    [lines, recommended.unmappedSolutions],
  );

  useEffect(() => {
    onWorkingDraftChange?.(draft);
  }, [draft, onWorkingDraftChange]);

  function emitCustomization(nextLines: QuoteLineEdit[] | null, nextInputs: QuoteInputs = inputs) {
    onQuoteCustomizationChange?.({
      packageTiers: selectedPackageTiers,
      lines: serializeQuoteLineEdits(nextLines),
      recommendedProductKey: recommendedKey,
      quoteInputs: {
        travel_km: nextInputs.travel_km,
        apply_weekend_surcharge: nextInputs.apply_weekend_surcharge,
        apply_emergency_surcharge: nextInputs.apply_emergency_surcharge,
        margin_percent_override: nextInputs.margin_percent_override,
      },
    });
  }

  const jobCity = assessmentJobCity(assessment);

  const packageComparisons = useMemo(
    () => buildPackageCostComparisons(catalog, draft),
    [catalog, draft],
  );
  const packageOffers = useMemo(
    () => packagesForAssessorQuote(packageComparisons),
    [packageComparisons],
  );
  const openPackageRow = useMemo(
    () => packageOffers.find((row) => row.package.id === openPackageId) ?? null,
    [packageOffers, openPackageId],
  );
  const unpricedPackages = (catalog.packages ?? []).filter(
    (p) => p.price_inr == null || p.price_inr < 0,
  );

  const quote = useMemo(
    () =>
      draft.items.length
        ? buildSafeHomeQuote(draft, plan, pricing, inputs, {
            suppliers,
            vendorContext: { jobCity },
          })
        : null,
    [draft, plan, pricing, inputs, suppliers, jobCity],
  );

  const reportText = useMemo(
    () =>
      buildQuoteReportText(assessment, categories, library, catalog, pricing, inputs, {
        packageTiers: selectedPackageTiers,
        draft,
        plan,
      }) ?? "",
    [assessment, categories, library, catalog, pricing, inputs, selectedPackageTiers, draft, plan],
  );

  const addableProducts = useMemo(() => {
    const used = new Set(lines.map((l) => l.productId));
    return (catalog.products ?? [])
      .filter((p) => !used.has(p.id))
      .slice()
      .sort(
        (a, b) =>
          (a.sort_order ?? 0) - (b.sort_order ?? 0) ||
          (a.product_code ?? a.name).localeCompare(b.product_code ?? b.name),
      );
  }, [catalog.products, lines]);

  function ensureEditable(): QuoteLineEdit[] {
    if (lineEdits) return lineEdits;
    const next = quoteLinesFromRecommended(recommended);
    setLineEdits(next);
    return next;
  }

  function toggleProduct(productId: string) {
    const base = ensureEditable();
    const next = base.map((line) =>
      line.productId === productId ? { ...line, included: !line.included } : line,
    );
    setLineEdits(next);
    emitCustomization(next);
  }

  function addProduct() {
    if (!addProductId) return;
    const product = catalog.products.find((p) => p.id === addProductId);
    if (!product) return;
    const base = ensureEditable();
    if (base.some((l) => l.productId === product.id)) return;
    const next: QuoteLineEdit[] = [
      ...base,
      {
        productId: product.id,
        included: true,
        source: "added",
        item: recommendationFromProduct(product),
      },
    ];
    setLineEdits(next);
    setAddProductId("");
    emitCustomization(next);
    onQuoteAction?.(`Added ${product.name} to quote.`);
  }

  function revertToRecommended() {
    setLineEdits(null);
    setAddProductId("");
    const nextInputs: QuoteInputs = {
      ...inputs,
      margin_percent_override: pricing.default_margin_percent,
    };
    setInputs(nextInputs);
    emitCustomization(null, nextInputs);
    onQuoteAction?.("Reverted to recommended product list and default margin.");
  }

  function toggleTier(tier: string) {
    onPackageTiersChange(
      selectedPackageTiers.includes(tier)
        ? selectedPackageTiers.filter((t) => t !== tier)
        : [...selectedPackageTiers, tier],
    );
  }

  function setInput<K extends keyof QuoteInputs>(key: K, value: QuoteInputs[K]) {
    const next = { ...inputs, [key]: value };
    setInputs(next);
    emitCustomization(lineEdits, next);
  }

  function copyQuote() {
    if (!reportText) {
      onQuoteAction?.("", "Nothing to copy — rate findings Unsafe or Acceptable first.");
      return;
    }
    navigator.clipboard
      .writeText(reportText)
      .then(() => onQuoteAction?.("Quote copied to clipboard."))
      .catch(() => onQuoteAction?.("", "Could not copy quote."));
  }

  function shareQuote() {
    if (!reportText) {
      onQuoteAction?.("", "Nothing to share — rate findings Unsafe or Acceptable first.");
      return;
    }
    const name = [assessment.clientFirstName, assessment.clientLastName].filter(Boolean).join(" ");
    if (navigator.share) {
      void navigator
        .share({
          title: `Home safety quote${name ? ` — ${name}` : ""}`,
          text: reportText,
        })
        .catch(() => undefined);
    } else {
      copyQuote();
    }
  }

  if (!fullPlan.entries.length) {
    return null;
  }

  if (!fullDraft.items.length) {
    return (
      <section className="card home-safety-section home-safety-quote-draft">
        <h2>Customer quote</h2>
        <p className="muted">
          The improvement plan has {fullPlan.entries.length} solution
          {fullPlan.entries.length === 1 ? "" : "s"}, but none are linked to catalog products yet.
        </p>
        {canOpen("/kushalaya/catalog") ? (
          <p className="muted home-safety-admin-link">
            <Link href="/kushalaya/catalog">Link products to solutions →</Link>
          </p>
        ) : null}
      </section>
    );
  }

  const includedCount = lines.filter((l) => l.included).length;
  const marginValue = inputs.margin_percent_override ?? pricing.default_margin_percent;

  return (
    <section className="card home-safety-section home-safety-quote-draft">
      <div className="home-safety-improvement-head">
        <h2>Customer quote</h2>
        {quote ? (
          <p className="muted home-safety-improvement-score">
            Grand total <strong>{formatInr(quote.grandTotalInr, "")}</strong>
            <span className="home-safety-improvement-gain">
              {" "}
              · {includedCount} SKU{includedCount === 1 ? "" : "s"}
            </span>
          </p>
        ) : (
          <p className="muted home-safety-improvement-score">
            {selectedPackageTiers.length
              ? "No SKUs selected for this quote"
              : "Select a package tier"}
          </p>
        )}
      </div>

      <p className="muted home-safety-section-hint">
        Start from the recommended list for the selected package tier. Deselect products, add
        catalog SKUs, and adjust margin within the allowed range. Use revert anytime to restore
        recommendations.
      </p>

      <fieldset className="ai-phase-tiers home-safety-quote-tiers">
        <legend>Package tiers</legend>
        {ACTIVE_TIERS.map((tier) => (
          <label key={tier} className="ai-phase-check">
            <input
              type="checkbox"
              checked={selectedPackageTiers.includes(tier)}
              onChange={() => toggleTier(tier)}
            />
            <span className="ai-phase-check-text">{TIER_LABELS[tier]}</span>
          </label>
        ))}
      </fieldset>
      {!selectedPackageTiers.length ? (
        <p className="error-text">Select at least one package tier to build the quote.</p>
      ) : (
        <p className="muted" style={{ marginTop: "0.35rem", fontSize: "0.85rem" }}>
          Active scope: <strong>{TIER_LABELS[scoped.scope] || scoped.scope}</strong>
          {" · "}
          {scoped.solutionIds.length} solution
          {scoped.solutionIds.length === 1 ? "" : "s"}
          {" · "}
          {includedCount} of {lines.length} SKU{lines.length === 1 ? "" : "s"} selected
          {isCustomized ? " · customized" : " · recommended"}
        </p>
      )}

      <div className="home-safety-quote-actions">
        <button
          type="button"
          className="primary"
          onClick={copyQuote}
          disabled={!reportText || !selectedPackageTiers.length}
        >
          Copy quote
        </button>
        <button
          type="button"
          className="secondary"
          onClick={shareQuote}
          disabled={!reportText || !selectedPackageTiers.length}
        >
          Share quote
        </button>
        <button
          type="button"
          className="secondary"
          onClick={revertToRecommended}
          disabled={!isCustomized && marginValue === pricing.default_margin_percent}
        >
          Revert to recommended
        </button>
      </div>

      <div className="home-safety-quote-inputs">
        <label className="home-safety-field">
          Travel (km)
          <input
            type="number"
            min={0}
            step={0.5}
            value={inputs.travel_km ?? 0}
            onChange={(e) => setInput("travel_km", Number(e.target.value))}
          />
        </label>
        <label className="home-safety-field">
          Labor hours
          <input
            type="number"
            min={0}
            step={0.5}
            placeholder={quote ? String(quote.laborHours) : "Auto"}
            value={inputs.labor_hours ?? ""}
            onChange={(e) =>
              setInput("labor_hours", e.target.value ? Number(e.target.value) : undefined)
            }
          />
        </label>
        {pricing.margin_type === "percent" ? (
          <label className="home-safety-field">
            Margin % ({pricing.min_margin_percent}–{pricing.max_margin_percent})
            <input
              type="number"
              min={pricing.min_margin_percent}
              max={pricing.max_margin_percent}
              step={1}
              value={marginValue}
              onChange={(e) =>
                setInput(
                  "margin_percent_override",
                  clampMargin(Number(e.target.value) || 0, pricing),
                )
              }
            />
          </label>
        ) : (
          <p className="muted" style={{ margin: 0, fontSize: "0.85rem" }}>
            Margin is fixed at {formatInr(pricing.fixed_margin_inr, "")} in pricing settings.
          </p>
        )}
        <label className="home-safety-check-inline">
          <input
            type="checkbox"
            checked={Boolean(inputs.apply_weekend_surcharge)}
            onChange={(e) => setInput("apply_weekend_surcharge", e.target.checked)}
          />
          <span>Weekend surcharge ({pricing.weekend_surcharge_percent}%)</span>
        </label>
        <label className="home-safety-check-inline">
          <input
            type="checkbox"
            checked={Boolean(inputs.apply_emergency_surcharge)}
            onChange={(e) => setInput("apply_emergency_surcharge", e.target.checked)}
          />
          <span>Emergency surcharge ({pricing.emergency_surcharge_percent}%)</span>
        </label>
      </div>

      <div className="home-safety-quote-add-row">
        <label className="home-safety-field home-safety-quote-add-field">
          Add catalog product
          <select
            value={addProductId}
            onChange={(e) => setAddProductId(e.target.value)}
            disabled={!addableProducts.length}
          >
            <option value="">
              {addableProducts.length ? "Select a product…" : "All catalog products already listed"}
            </option>
            {addableProducts.map((p) => (
              <option key={p.id} value={p.id}>
                {(p.product_code ? `${p.product_code} — ` : "") + withPublicBrand(p.name)}
                {p.price_inr != null ? ` (${formatInr(p.price_inr, "")})` : ""}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="secondary"
          onClick={addProduct}
          disabled={!addProductId}
        >
          Add to quote
        </button>
      </div>

      {!lines.length ? (
        <p className="muted">No catalog SKUs fall in the selected package tier scope.</p>
      ) : (
        <div className="home-safety-quote-table-wrap">
          <table className="data-table home-safety-quote-table">
            <thead>
              <tr>
                <th className="home-safety-quote-include-col">Include</th>
                <th>SKU</th>
                <th>Product</th>
                <th>Solutions</th>
                {suppliers ? <th>Vendor cost</th> : null}
                <th>Est.</th>
              </tr>
            </thead>
            <tbody>
              {lines.map((line) => {
                const item = line.item;
                const vendorCost =
                  suppliers &&
                  supplierCostBasisInr(suppliers, item.product.id, item.quantity);
                const autoVendor =
                  suppliers &&
                  selectVendorOffer(suppliers, item.product.id, {
                    quantity: item.quantity,
                  });
                return (
                  <tr
                    key={line.productId}
                    className={line.included ? undefined : "home-safety-quote-row-excluded"}
                  >
                    <td>
                      <label className="home-safety-quote-include">
                        <input
                          type="checkbox"
                          checked={line.included}
                          onChange={() => toggleProduct(line.productId)}
                          aria-label={`Include ${item.product.name}`}
                        />
                      </label>
                    </td>
                    <td>
                      <code className="home-safety-quote-sku">
                        {item.product.product_code ?? "—"}
                      </code>
                      {line.source === "added" ? (
                        <span className="home-safety-quote-added-tag">Added</span>
                      ) : null}
                    </td>
                    <td>
                      <strong>{item.product.name}</strong>
                    </td>
                    <td className="home-safety-quote-solutions">
                      {item.solutionIds.length
                        ? item.solutionIds.map((id) => (
                            <span key={id} className="home-safety-quote-solution-tag">
                              {id}
                            </span>
                          ))
                        : (
                          <span className="muted">Assessor-added</span>
                        )}
                    </td>
                    {suppliers ? (
                      <td
                        className="muted home-safety-quote-vendor-cost"
                        style={{ fontSize: "0.85rem" }}
                      >
                        {vendorCost != null ? (
                          <>
                            from {formatInr(vendorCost, "")}
                            {autoVendor ? (
                              <div>
                                → {autoVendor.supplier.name} ({autoVendor.reason})
                              </div>
                            ) : null}
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                    ) : null}
                    <td className="home-safety-quote-price">
                      {item.lineTotalInr != null
                        ? formatInr(item.lineTotalInr, "")
                        : item.product.price_label || "Quote"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {quote && (
        <dl className="home-safety-quote-breakdown">
          <div>
            <dt>Products</dt>
            <dd>{formatInr(quote.productTotalInr, "")}</dd>
          </div>
          {quote.vendorProductCostInr != null && (
            <>
              <div>
                <dt>Vendor product cost</dt>
                <dd className="muted">{formatInr(quote.vendorProductCostInr, "")}</dd>
              </div>
              {quote.grossProductMarginInr != null && (
                <div>
                  <dt>Gross product margin</dt>
                  <dd className="muted">{formatInr(quote.grossProductMarginInr, "")}</dd>
                </div>
              )}
            </>
          )}
          <div>
            <dt>
              Labor ({quote.laborHours}h × {formatInr(quote.laborRatePerHourInr, "")}/h)
            </dt>
            <dd>{formatInr(quote.laborTotalInr, "")}</dd>
          </div>
          <div>
            <dt>Travel ({quote.travelKm} km)</dt>
            <dd>{formatInr(quote.travelTotalInr, "")}</dd>
          </div>
          <div>
            <dt>Consumables</dt>
            <dd>{formatInr(quote.consumablesInr, "")}</dd>
          </div>
          {quote.miscellaneousInr > 0 && (
            <div>
              <dt>Other</dt>
              <dd>{formatInr(quote.miscellaneousInr, "")}</dd>
            </div>
          )}
          {quote.weekendSurchargeInr > 0 && (
            <div>
              <dt>Weekend surcharge</dt>
              <dd>{formatInr(quote.weekendSurchargeInr, "")}</dd>
            </div>
          )}
          {quote.emergencySurchargeInr > 0 && (
            <div>
              <dt>Emergency surcharge</dt>
              <dd>{formatInr(quote.emergencySurchargeInr, "")}</dd>
            </div>
          )}
          <div>
            <dt>
              Margin (
              {quote.marginType === "fixed" ? "fixed" : `${quote.marginPercent}%`})
            </dt>
            <dd>{formatInr(quote.marginAmountInr, "")}</dd>
          </div>
          <div>
            <dt>GST ({quote.gstPercent}%)</dt>
            <dd>{formatInr(quote.gstAmountInr, "")}</dd>
          </div>
          {quote.roundOffInr !== 0 && (
            <div>
              <dt>Round-off</dt>
              <dd>{formatInr(quote.roundOffInr, "")}</dd>
            </div>
          )}
          <div className="home-safety-quote-breakdown-total">
            <dt>Grand total</dt>
            <dd>{formatInr(quote.grandTotalInr, "")}</dd>
          </div>
        </dl>
      )}

      {(packageOffers.length > 0 || unpricedPackages.length > 0) && (
        <div className="home-safety-package-savings">
          <h3 style={{ marginTop: "1.25rem", marginBottom: "0.35rem" }}>
            Package cost difference
          </h3>
          <p className="muted" style={{ marginTop: 0, fontSize: "0.9rem" }}>
            Compare current quote products with priced catalog packages. Tap a package to see
            included products.
            {canOpen("/kushalaya/catalog") ? (
              <>
                {" "}Set each package&apos;s price in <Link href="/kushalaya/catalog">Catalog</Link>.
              </>
            ) : null}
          </p>
          {packageOffers.length > 0 ? (
            <ul className="home-safety-package-savings-list">
              {packageOffers.map((row) => {
                const saveRec = row.savingsVsRecommendedInr;
                const saveFull = row.savingsVsFullBundleInr;
                return (
                  <li key={row.package.id}>
                    <button
                      type="button"
                      className="home-safety-package-savings-card home-safety-package-savings-card-btn"
                      onClick={() => setOpenPackageId(row.package.id)}
                    >
                      <div className="home-safety-package-savings-head">
                        <strong>{row.package.name}</strong>
                        <span>{formatInr(row.packagePriceInr, "")}</span>
                      </div>
                      {row.package.tagline ? (
                        <p className="muted" style={{ margin: "0.25rem 0", fontSize: "0.85rem" }}>
                          {row.package.tagline}
                        </p>
                      ) : null}
                      {row.fullBundleRetailInr != null ? (
                        <p style={{ margin: "0.35rem 0", fontSize: "0.9rem" }}>
                          Full list ({row.fullBundleProductCount} items):{" "}
                          {formatInr(row.fullBundleRetailInr, "")}
                          {saveFull != null && saveFull > 0 ? (
                            <>
                              {" "}
                              · <strong>save {formatInr(saveFull, "")}</strong> vs package
                            </>
                          ) : null}
                          {saveFull != null && saveFull < 0 ? (
                            <>
                              {" "}
                              · package is {formatInr(-saveFull, "")} more than list
                            </>
                          ) : null}
                        </p>
                      ) : null}
                      {row.overlapItemCount > 0 && row.recommendedOverlapInr != null ? (
                        <p style={{ margin: "0.35rem 0", fontSize: "0.9rem" }}>
                          Quote overlap ({row.overlapItemCount} SKU):{" "}
                          {formatInr(row.recommendedOverlapInr, "")}
                          {saveRec != null && saveRec > 0 ? (
                            <>
                              {" "}
                              ·{" "}
                              <strong className="home-safety-package-save">
                                customer saves {formatInr(saveRec, "")} with package
                              </strong>
                            </>
                          ) : null}
                          {saveRec != null && saveRec < 0 ? (
                            <>
                              {" "}
                              · package is {formatInr(-saveRec, "")} more than those items alone
                            </>
                          ) : null}
                          {saveRec === 0 ? <> · same as overlap</> : null}
                        </p>
                      ) : (
                        <p className="muted" style={{ margin: "0.35rem 0", fontSize: "0.85rem" }}>
                          No overlap with current quote
                          {row.package.highlight ? " (highlighted package)" : ""}.
                        </p>
                      )}
                      <span className="home-safety-package-savings-hint">
                        View included products
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : null}
          {unpricedPackages.length > 0 ? (
            <p className="muted" style={{ marginTop: "0.75rem", fontSize: "0.85rem" }}>
              {unpricedPackages.length} package(s) have no price set — add{" "}
              <code>price_inr</code> to compare:{" "}
              {unpricedPackages.map((p) => p.name).join(", ")}.
            </p>
          ) : null}
        </div>
      )}

      {openPackageRow ? (
        <PackageContentsModal
          row={openPackageRow}
          catalog={catalog}
          onClose={() => setOpenPackageId(null)}
        />
      ) : null}

      {draft.unmappedSolutions.length > 0 && (
        <div className="home-safety-quote-unmapped">
          <h3>Solutions without catalog products</h3>
          <ul className="home-safety-improvement-list">
            {draft.unmappedSolutions.map((s) => (
              <li key={s.id} className="muted">
                <code>{s.id}</code> — {s.finding}
              </li>
            ))}
          </ul>
        </div>
      )}

      <details className="home-safety-improvement-text">
        <summary className="muted">Plain-text quote (for copy / report)</summary>
        <pre>{reportText}</pre>
      </details>

      {canOpen("/kushalaya/catalog") ? (
        <p className="muted home-safety-admin-link">
          <Link href="/kushalaya/catalog">Edit product catalog →</Link>
        </p>
      ) : null}
    </section>
  );
}
