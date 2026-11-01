import type { CatalogProduct, SafetyCatalog } from "./catalog-types";
import { productUnitPriceInr } from "./catalog";
import { productsForSolution } from "./catalog-product-seed";
import type { ImprovementPlan, ImprovementPlanEntry } from "./improvement-plan";
import type { SolutionPriority } from "./solution-types";
import { SOLUTION_PRIORITY_ORDER } from "./solution-types";

export interface ProductRecommendation {
  product: CatalogProduct;
  solutionIds: string[];
  solutionFindings: string[];
  quantity: number;
  unitPriceInr: number | null;
  lineTotalInr: number | null;
}

export interface UnmappedSolution {
  id: string;
  finding: string;
  name?: string;
  priority: SolutionPriority;
}

export interface ProductQuoteDraft {
  items: ProductRecommendation[];
  subtotalInr: number | null;
  pricedItemCount: number;
  unmappedSolutions: UnmappedSolution[];
}

function priorityRank(priority: SolutionPriority): number {
  const index = SOLUTION_PRIORITY_ORDER.indexOf(priority);
  return index >= 0 ? index : SOLUTION_PRIORITY_ORDER.length;
}

function entryPriorityRank(entry: ImprovementPlanEntry): number {
  return priorityRank(entry.solution.priority);
}

export function buildProductRecommendations(
  plan: ImprovementPlan,
  catalog: SafetyCatalog,
): ProductQuoteDraft {
  const byProductId = new Map<
    string,
    {
      product: CatalogProduct;
      solutionIds: Set<string>;
      solutionFindings: Set<string>;
      minPriority: number;
    }
  >();
  const unmappedSolutions: UnmappedSolution[] = [];

  for (const entry of plan.entries) {
    const products = productsForSolution(catalog.products, entry.solution.id);
    if (!products.length) {
      unmappedSolutions.push({
        id: entry.solution.id,
        finding: entry.solution.finding,
        name: entry.solution.name,
        priority: entry.solution.priority,
      });
      continue;
    }

    const rank = entryPriorityRank(entry);
    for (const product of products) {
      const existing = byProductId.get(product.id);
      if (!existing) {
        byProductId.set(product.id, {
          product,
          solutionIds: new Set([entry.solution.id]),
          solutionFindings: new Set([entry.solution.finding]),
          minPriority: rank,
        });
        continue;
      }
      existing.solutionIds.add(entry.solution.id);
      existing.solutionFindings.add(entry.solution.finding);
      existing.minPriority = Math.min(existing.minPriority, rank);
    }
  }

  const items: ProductRecommendation[] = [...byProductId.values()]
    .map(({ product, solutionIds, solutionFindings, minPriority }) => {
      const quantity = 1;
      const unitPriceInr = productUnitPriceInr(product);
      return {
        product,
        solutionIds: [...solutionIds].sort(),
        solutionFindings: [...solutionFindings],
        quantity,
        unitPriceInr,
        lineTotalInr: unitPriceInr != null ? unitPriceInr * quantity : null,
        minPriority,
      };
    })
    .sort(
      (a, b) =>
        a.minPriority - b.minPriority ||
        (a.product.sort_order ?? 0) - (b.product.sort_order ?? 0) ||
        (a.product.product_code ?? "").localeCompare(b.product.product_code ?? ""),
    )
    .map(({ minPriority: _minPriority, ...item }) => item);

  const priced = items.filter((i) => i.lineTotalInr != null);
  const subtotalInr = priced.length
    ? priced.reduce((sum, i) => sum + (i.lineTotalInr ?? 0), 0)
    : null;

  unmappedSolutions.sort(
    (a, b) => priorityRank(a.priority) - priorityRank(b.priority) || a.id.localeCompare(b.id),
  );

  return {
    items,
    subtotalInr,
    pricedItemCount: priced.length,
    unmappedSolutions,
  };
}

export function formatProductQuoteDraftText(draft: ProductQuoteDraft): string {
  if (!draft.items.length) {
    return "No catalog products matched the improvement plan.";
  }

  const lines: string[] = [
    "PRODUCT LINE ITEMS",
    "",
  ];

  for (const item of draft.items) {
    const code = item.product.product_code ?? item.product.id;
    const price =
      item.lineTotalInr != null
        ? `₹${item.lineTotalInr.toLocaleString("en-IN")}`
        : item.product.price_label || "Quote";
    lines.push(`  ${code} — ${item.product.name}`);
    lines.push(`    Solutions: ${item.solutionIds.join(", ") || "Assessor-added"}`);
    lines.push(`    Unit: ${price}`);
  }

  if (draft.subtotalInr != null) {
    lines.push(
      "",
      `Subtotal (${draft.pricedItemCount} priced item${draft.pricedItemCount === 1 ? "" : "s"}): ₹${draft.subtotalInr.toLocaleString("en-IN")}`,
    );
  } else {
    lines.push("", "Subtotal: Quote on visit (no priced items in catalog).");
  }

  if (draft.unmappedSolutions.length) {
    lines.push("", "Solutions without catalog products:");
    for (const s of draft.unmappedSolutions) {
      lines.push(`  ${s.id} — ${s.finding}`);
    }
  }

  return lines.join("\n").trim();
}

/** Build a quote line from a catalog product (assessor-added). */
export function recommendationFromProduct(
  product: CatalogProduct,
  quantity = 1,
): ProductRecommendation {
  const unitPriceInr = productUnitPriceInr(product);
  return {
    product,
    solutionIds: [...(product.solution_ids ?? [])].sort(),
    solutionFindings: [],
    quantity,
    unitPriceInr,
    lineTotalInr: unitPriceInr != null ? unitPriceInr * quantity : null,
  };
}

/** Recompute draft totals from an item list. */
export function rebuildProductQuoteDraft(
  items: ProductRecommendation[],
  unmappedSolutions: UnmappedSolution[] = [],
): ProductQuoteDraft {
  const priced = items.filter((i) => i.lineTotalInr != null);
  const subtotalInr = priced.length
    ? priced.reduce((sum, i) => sum + (i.lineTotalInr ?? 0), 0)
    : null;
  return {
    items,
    subtotalInr,
    pricedItemCount: priced.length,
    unmappedSolutions,
  };
}

export type QuoteLineEdit = {
  productId: string;
  included: boolean;
  source: "recommended" | "added";
  item: ProductRecommendation;
};

export function quoteLinesFromRecommended(draft: ProductQuoteDraft): QuoteLineEdit[] {
  return draft.items.map((item) => ({
    productId: item.product.id,
    included: true,
    source: "recommended" as const,
    item,
  }));
}

export function draftFromQuoteLines(
  lines: QuoteLineEdit[],
  unmappedSolutions: UnmappedSolution[] = [],
): ProductQuoteDraft {
  return rebuildProductQuoteDraft(
    lines.filter((l) => l.included).map((l) => l.item),
    unmappedSolutions,
  );
}

export function recommendedProductIdsKey(draft: ProductQuoteDraft): string {
  return draft.items.map((i) => i.product.id).join("|");
}

export function serializeQuoteLineEdits(
  lines: QuoteLineEdit[] | null,
): Array<{ productId: string; included: boolean; source: "recommended" | "added" }> | null {
  if (!lines) return null;
  return lines.map(({ productId, included, source }) => ({ productId, included, source }));
}

export function hydrateQuoteLineEdits(
  saved: Array<{ productId: string; included: boolean; source: "recommended" | "added" }> | null | undefined,
  recommended: ProductQuoteDraft,
  catalog: SafetyCatalog,
): QuoteLineEdit[] | null {
  if (!saved?.length) return null;
  const byId = new Map(recommended.items.map((i) => [i.product.id, i]));
  const out: QuoteLineEdit[] = [];
  for (const row of saved) {
    let item = byId.get(row.productId);
    if (!item) {
      const product = catalog.products.find((p) => p.id === row.productId);
      if (!product) continue;
      item = recommendationFromProduct(product);
    }
    out.push({
      productId: row.productId,
      included: row.included,
      source: row.source,
      item,
    });
  }
  return out.length ? out : null;
}
