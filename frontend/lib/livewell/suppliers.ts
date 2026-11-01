import { DEFAULT_SUPPLIER_DIRECTORY } from "./supplier-defaults";
import type {
  ProductSupplierOffer,
  PartnerRole,
  PartnerTier,
  Supplier,
  SupplierDirectory,
} from "./supplier-types";
import { readLocalStorageWithLegacy, removeLocalStorageKeys } from "./legacyStorage";

const STORAGE_KEY = "safehome_home_safety_suppliers_v1";
const LEGACY_STORAGE_KEYS = ["eldercare_home_safety_suppliers_v1"];

function offerId(productId: string, supplierId: string): string {
  return `offer_${productId}_${supplierId}`;
}

function normalizeRoles(raw: unknown): PartnerRole[] {
  const parts = Array.isArray(raw)
    ? raw.map((p) => String(p).trim().toLowerCase())
    : String(raw ?? "")
        .split(/[,|]/)
        .map((p) => p.trim().toLowerCase());
  const roles: PartnerRole[] = [];
  for (const role of parts) {
    if ((role === "supplier" || role === "installer") && !roles.includes(role)) {
      roles.push(role);
    }
  }
  return roles.length ? roles : ["supplier"];
}

function normalizeSupplier(raw: Partial<Supplier>, index: number): Supplier | null {
  const id = raw.id?.trim();
  const name = raw.name?.trim();
  if (!id || !name) return null;
  let rating: number | null = null;
  if (raw.rating != null && !Number.isNaN(Number(raw.rating))) {
    rating = Math.min(5, Math.max(0, Number(raw.rating)));
  }
  let rolling: number | null = null;
  if (raw.rolling_rating != null && !Number.isNaN(Number(raw.rolling_rating))) {
    rolling = Math.min(5, Math.max(0, Number(raw.rolling_rating)));
  }
  const tierRaw = String(raw.partner_tier ?? "").trim().toLowerCase();
  const partner_tier: PartnerTier =
    tierRaw === "founding_platinum" || tierRaw === "gold" || tierRaw === "silver"
      ? tierRaw
      : "";
  return {
    id,
    name,
    contact: raw.contact?.trim() ?? "",
    phone: raw.phone?.trim() ?? "",
    email: raw.email?.trim() ?? "",
    city: raw.city?.trim() ?? "",
    rating,
    roles: normalizeRoles(raw.roles),
    category: raw.category?.trim() ?? "",
    partner_tier,
    rolling_rating: rolling,
    rolling_rating_count: Math.max(0, Number(raw.rolling_rating_count) || 0),
    rolling_window: Math.min(20, Math.max(1, Number(raw.rolling_window) || 5)),
    active: raw.active !== false,
    sort_order: raw.sort_order ?? index,
  };
}

function resolvePreferredOffers(offers: ProductSupplierOffer[]): ProductSupplierOffer[] {
  const byProduct = new Map<string, ProductSupplierOffer[]>();
  for (const offer of offers) {
    const list = byProduct.get(offer.product_id) ?? [];
    list.push(offer);
    byProduct.set(offer.product_id, list);
  }

  const resolved: ProductSupplierOffer[] = [];
  for (const productOffers of byProduct.values()) {
    const preferred = productOffers.filter((o) => o.preferred);
    if (preferred.length > 1) {
      const keep = preferred.reduce((best, o) =>
        o.supplier_cost_inr < best.supplier_cost_inr ? o : best,
      );
      for (const offer of productOffers) {
        resolved.push({ ...offer, preferred: offer.id === keep.id });
      }
    } else {
      resolved.push(...productOffers);
    }
  }
  return resolved.sort((a, b) =>
    a.product_id.localeCompare(b.product_id) || a.supplier_id.localeCompare(b.supplier_id),
  );
}

function normalizeOffer(
  raw: Partial<ProductSupplierOffer>,
  supplierIds: Set<string>,
): ProductSupplierOffer | null {
  const productId = raw.product_id?.trim();
  const supplierId = raw.supplier_id?.trim();
  if (!productId || !supplierId || !supplierIds.has(supplierId)) return null;
  const id = raw.id?.trim() || offerId(productId, supplierId);
  return {
    id,
    product_id: productId,
    supplier_id: supplierId,
    supplier_cost_inr: Math.max(0, Number(raw.supplier_cost_inr) || 0),
    preferred: Boolean(raw.preferred),
    moq: Math.max(1, Number(raw.moq) || 1),
    lead_time_days: Math.max(0, Number(raw.lead_time_days) || 0),
    vendor_sku: raw.vendor_sku?.trim() ?? "",
    active: raw.active !== false,
  };
}

export function normalizeSupplierDirectory(
  raw: {
    suppliers?: Array<Partial<Supplier>>;
    offers?: Array<Partial<ProductSupplierOffer>>;
  },
  options?: { validProductIds?: Set<string> },
): SupplierDirectory {
  const suppliers = (raw.suppliers ?? [])
    .map((s, i) => normalizeSupplier(s, i))
    .filter((s): s is Supplier => Boolean(s))
    .sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name));

  const supplierIds = new Set(suppliers.map((s) => s.id));
  const seen = new Set<string>();
  const offers: ProductSupplierOffer[] = [];

  for (const item of raw.offers ?? []) {
    const offer = normalizeOffer(item, supplierIds);
    if (!offer) continue;
    const pair = `${offer.product_id}::${offer.supplier_id}`;
    if (seen.has(pair)) continue;
    if (options?.validProductIds && !options.validProductIds.has(offer.product_id)) continue;
    seen.add(pair);
    offers.push(offer);
  }

  return {
    suppliers,
    offers: resolvePreferredOffers(offers),
  };
}

export function getLocalSupplierDirectory(): SupplierDirectory {
  if (typeof window === "undefined") return DEFAULT_SUPPLIER_DIRECTORY;
  try {
    const raw = readLocalStorageWithLegacy(STORAGE_KEY, LEGACY_STORAGE_KEYS);
    if (!raw) return DEFAULT_SUPPLIER_DIRECTORY;
    return normalizeSupplierDirectory(JSON.parse(raw) as SupplierDirectory);
  } catch {
    return DEFAULT_SUPPLIER_DIRECTORY;
  }
}

export function saveLocalSupplierDirectory(directory: SupplierDirectory): SupplierDirectory {
  const normalized = normalizeSupplierDirectory(directory);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
  removeLocalStorageKeys(...LEGACY_STORAGE_KEYS);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("home-safety-suppliers-updated"));
  }
  return normalized;
}

export function resetLocalSupplierDirectory(): SupplierDirectory {
  removeLocalStorageKeys(STORAGE_KEY, ...LEGACY_STORAGE_KEYS);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("home-safety-suppliers-updated"));
  }
  return DEFAULT_SUPPLIER_DIRECTORY;
}

export function offersForProduct(
  directory: SupplierDirectory,
  productId: string,
): ProductSupplierOffer[] {
  return directory.offers.filter((o) => o.product_id === productId && o.active);
}

export function supplierById(directory: SupplierDirectory, supplierId: string): Supplier | undefined {
  return directory.suppliers.find((s) => s.id === supplierId && s.active);
}
