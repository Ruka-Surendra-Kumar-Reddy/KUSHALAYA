/**
 * Package vs à-la-carte comparison for assessor quotes.
 * Package sell price comes from catalog `packages[].price_inr`.
 * À-la-carte uses recommended quote line prices for overlapping SKUs,
 * plus full bundle retail (all products in the package) for list savings.
 */

import { formatInr, productUnitPriceInr } from "./catalog";
import type { SafetyCatalog, ServicePackage } from "./catalog-types";
import type { ProductQuoteDraft } from "./product-recommendations";

export interface PackageCostComparison {
  package: ServicePackage;
  packagePriceInr: number;
  /** Sum of catalog unit prices for every product listed on the package. */
  fullBundleRetailInr: number | null;
  fullBundlePricedCount: number;
  fullBundleProductCount: number;
  /** Save vs buying every package SKU separately (list / marketing). */
  savingsVsFullBundleInr: number | null;
  /** Recommended quote items whose product is included in this package. */
  overlapItemCount: number;
  overlapProductIds: string[];
  /** À-la-carte total for overlapping recommended lines. */
  recommendedOverlapInr: number | null;
  /** recommendedOverlap − package price (positive = package cheaper for those items). */
  savingsVsRecommendedInr: number | null;
  /** Products in the package that are not in the current recommendation. */
  extraProductIds: string[];
  /** Recommended products not covered by this package. */
  uncoveredRecommendedProductIds: string[];
  /** Share of recommended SKUs covered (0–1). */
  coverageRatio: number;
}

function packageProductIdSet(pkg: ServicePackage): Set<string> {
  return new Set(pkg.product_ids.filter(Boolean));
}

function fullBundleRetail(
  catalog: SafetyCatalog,
  pkg: ServicePackage,
): { total: number | null; pricedCount: number; productCount: number } {
  const map = new Map(catalog.products.map((p) => [p.id, p]));
  let total = 0;
  let pricedCount = 0;
  let productCount = 0;
  for (const id of pkg.product_ids) {
    const product = map.get(id);
    if (!product) continue;
    productCount += 1;
    const unit = productUnitPriceInr(product);
    if (unit == null) continue;
    pricedCount += 1;
    total += unit;
  }
  return {
    total: pricedCount > 0 ? total : null,
    pricedCount,
    productCount,
  };
}

/** Rank packages most relevant to this quote first (coverage, then savings). */
export function comparePackageOffers(
  a: PackageCostComparison,
  b: PackageCostComparison,
): number {
  if (b.coverageRatio !== a.coverageRatio) return b.coverageRatio - a.coverageRatio;
  const saveA = a.savingsVsRecommendedInr ?? a.savingsVsFullBundleInr ?? -Infinity;
  const saveB = b.savingsVsRecommendedInr ?? b.savingsVsFullBundleInr ?? -Infinity;
  if (saveB !== saveA) return saveB - saveA;
  return a.package.sort_order - b.package.sort_order;
}

export function buildPackageCostComparisons(
  catalog: SafetyCatalog,
  draft: ProductQuoteDraft,
): PackageCostComparison[] {
  const draftByProduct = new Map(draft.items.map((item) => [item.product.id, item]));
  const recommendedIds = [...draftByProduct.keys()];
  const comparisons: PackageCostComparison[] = [];

  for (const pkg of catalog.packages ?? []) {
    if (pkg.price_inr == null || pkg.price_inr < 0) continue;
    if (!pkg.product_ids?.length) continue;

    const inPackage = packageProductIdSet(pkg);
    const bundle = fullBundleRetail(catalog, pkg);

    const overlapIds = recommendedIds.filter((id) => inPackage.has(id));
    let recommendedOverlapInr: number | null = null;
    let overlapPriced = 0;
    let overlapSum = 0;
    for (const id of overlapIds) {
      const line = draftByProduct.get(id);
      if (line?.lineTotalInr == null) continue;
      overlapPriced += 1;
      overlapSum += line.lineTotalInr;
    }
    if (overlapPriced > 0) recommendedOverlapInr = overlapSum;

    const extraProductIds = [...inPackage].filter((id) => !draftByProduct.has(id));
    const uncoveredRecommendedProductIds = recommendedIds.filter((id) => !inPackage.has(id));
    const coverageRatio = recommendedIds.length
      ? overlapIds.length / recommendedIds.length
      : 0;

    const savingsVsFullBundleInr =
      bundle.total != null ? bundle.total - pkg.price_inr : null;
    const savingsVsRecommendedInr =
      recommendedOverlapInr != null ? recommendedOverlapInr - pkg.price_inr : null;

    comparisons.push({
      package: pkg,
      packagePriceInr: pkg.price_inr,
      fullBundleRetailInr: bundle.total,
      fullBundlePricedCount: bundle.pricedCount,
      fullBundleProductCount: bundle.productCount,
      savingsVsFullBundleInr,
      overlapItemCount: overlapIds.length,
      overlapProductIds: overlapIds,
      recommendedOverlapInr,
      savingsVsRecommendedInr,
      extraProductIds,
      uncoveredRecommendedProductIds,
      coverageRatio,
    });
  }

  return comparisons.sort(comparePackageOffers);
}

/** Packages that touch the recommendation, plus highlighted ones with a price. */
export function packagesForAssessorQuote(
  comparisons: PackageCostComparison[],
): PackageCostComparison[] {
  const relevant = comparisons.filter(
    (c) => c.overlapItemCount > 0 || c.package.highlight,
  );
  return (relevant.length ? relevant : comparisons).slice(0, 6);
}

export function formatPackageCostDifference(
  comparison: PackageCostComparison,
): string {
  const name = comparison.package.name;
  const pkgPrice = formatInr(comparison.packagePriceInr, "");
  const lines: string[] = [`${name} — package ${pkgPrice}`];

  if (comparison.fullBundleRetailInr != null) {
    const bundle = formatInr(comparison.fullBundleRetailInr, "");
    const save = comparison.savingsVsFullBundleInr ?? 0;
    if (save > 0) {
      lines.push(
        `  Full list (${comparison.fullBundleProductCount} items): ${bundle} → save ${formatInr(save, "")} vs package`,
      );
    } else if (save < 0) {
      lines.push(
        `  Full list (${comparison.fullBundleProductCount} items): ${bundle} → package is ${formatInr(-save, "")} more (includes bundling / membership value)`,
      );
    } else {
      lines.push(`  Full list: ${bundle} (same as package)`);
    }
  }

  if (comparison.overlapItemCount > 0 && comparison.recommendedOverlapInr != null) {
    const ala = formatInr(comparison.recommendedOverlapInr, "");
    const save = comparison.savingsVsRecommendedInr ?? 0;
    lines.push(
      `  Recommended overlap (${comparison.overlapItemCount} SKU): ${ala}`,
    );
    if (save > 0) {
      lines.push(`  Cost difference: customer saves ${formatInr(save, "")} with package`);
    } else if (save < 0) {
      lines.push(
        `  Cost difference: package is ${formatInr(-save, "")} more than those recommended items alone`,
      );
    } else {
      lines.push(`  Cost difference: same as recommended overlap`);
    }
    if (comparison.extraProductIds.length) {
      lines.push(
        `  Package also includes ${comparison.extraProductIds.length} item(s) beyond this quote`,
      );
    }
    if (comparison.uncoveredRecommendedProductIds.length) {
      lines.push(
        `  Still needed à la carte: ${comparison.uncoveredRecommendedProductIds.length} recommended SKU(s)`,
      );
    }
  } else if (comparison.overlapItemCount === 0) {
    lines.push(`  No overlap with current recommendations`);
  }

  return lines.join("\n");
}

export function formatPackageComparisonsText(
  comparisons: PackageCostComparison[],
): string {
  const rows = packagesForAssessorQuote(comparisons);
  if (!rows.length) {
    return [
      "PACKAGE OPTIONS",
      "",
      "No priced packages configured. Set package price_inr in Catalog / Master Data.",
    ].join("\n");
  }
  return ["PACKAGE OPTIONS (cost difference vs à la carte)", "", ...rows.map(formatPackageCostDifference)].join(
    "\n",
  );
}
