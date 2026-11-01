import type { CatalogProduct } from "./catalog-types";
import { DEFAULT_SAFETY_CATALOG } from "./catalog-defaults";

/**
 * Product rows mirrored from the master spreadsheet.
 * Prefer editing Kushalaya_Configuration.xlsx, then:
 *   python backend/scripts/sync_catalog_defaults_from_workbook.py
 */
export const SEEDED_CATALOG_PRODUCTS: CatalogProduct[] = DEFAULT_SAFETY_CATALOG.products;

export function productsForSolution(
  products: CatalogProduct[],
  solutionId: string,
): CatalogProduct[] {
  return products.filter((p) => (p.solution_ids ?? []).includes(solutionId));
}
