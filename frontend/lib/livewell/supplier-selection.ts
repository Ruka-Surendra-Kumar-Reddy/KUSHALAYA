import type {
  ProductSupplierOffer,
  SelectedVendorOffer,
  Supplier,
  SupplierDirectory,
  VendorSelectionContext,
} from "./supplier-types";
import { offersForProduct, supplierById } from "./suppliers";

function cityMatches(supplier: Supplier, jobCity?: string): boolean {
  if (!jobCity?.trim()) return true;
  if (!supplier.city?.trim()) return true;
  return supplier.city.trim().toLowerCase() === jobCity.trim().toLowerCase();
}

function offerEligible(offer: ProductSupplierOffer, quantity: number): boolean {
  return offer.active && quantity >= offer.moq;
}

function compareOffers(
  a: ProductSupplierOffer,
  b: ProductSupplierOffer,
  suppliers: Map<string, Supplier>,
): number {
  if (a.preferred !== b.preferred) return a.preferred ? -1 : 1;
  if (a.supplier_cost_inr !== b.supplier_cost_inr) {
    return a.supplier_cost_inr - b.supplier_cost_inr;
  }
  if (a.lead_time_days !== b.lead_time_days) {
    return a.lead_time_days - b.lead_time_days;
  }
  const ratingA = suppliers.get(a.supplier_id)?.rating ?? 0;
  const ratingB = suppliers.get(b.supplier_id)?.rating ?? 0;
  return ratingB - ratingA;
}

/** Pick the best vendor offer for procurement (not shown on customer quote). */
export function selectVendorOffer(
  directory: SupplierDirectory,
  productId: string,
  context: VendorSelectionContext = {},
): SelectedVendorOffer | null {
  const quantity = Math.max(1, context.quantity ?? 1);
  const supplierMap = new Map(directory.suppliers.map((s) => [s.id, s]));

  const candidates = offersForProduct(directory, productId)
    .filter((offer) => offerEligible(offer, quantity))
    .filter((offer) => {
      const supplier = supplierMap.get(offer.supplier_id);
      return supplier?.active && cityMatches(supplier, context.jobCity);
    });

  if (!candidates.length) return null;

  const sorted = [...candidates].sort((a, b) => compareOffers(a, b, supplierMap));
  const offer = sorted[0];
  const supplier = supplierMap.get(offer.supplier_id);
  if (!supplier) return null;

  let reason = "lowest cost";
  if (offer.preferred) reason = "preferred vendor";
  else if (sorted.length > 1 && sorted[1].supplier_cost_inr === offer.supplier_cost_inr) {
    reason = "shortest lead time";
  }

  return { offer, supplier, reason };
}

/** Preferred vendor cost, or lowest active offer cost for margin hints. */
export function supplierCostBasisInr(
  directory: SupplierDirectory,
  productId: string,
  quantity = 1,
): number | null {
  const offers = offersForProduct(directory, productId).filter((o) =>
    offerEligible(o, quantity),
  );
  if (!offers.length) return null;
  const preferred = offers.find((o) => o.preferred);
  if (preferred) return preferred.supplier_cost_inr;
  return Math.min(...offers.map((o) => o.supplier_cost_inr));
}

export function minActiveSupplierCostInr(
  directory: SupplierDirectory,
  productId: string,
): number | null {
  const offers = offersForProduct(directory, productId);
  if (!offers.length) return null;
  return Math.min(...offers.map((o) => o.supplier_cost_inr));
}
