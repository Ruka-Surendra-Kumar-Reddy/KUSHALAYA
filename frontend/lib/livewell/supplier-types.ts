/** LiveWell360 partner directory — suppliers (product) and installers (field). */

export type PartnerRole = "supplier" | "installer";
export type PartnerTier = "" | "founding_platinum" | "gold" | "silver";

export interface Supplier {
  id: string;
  name: string;
  contact: string;
  phone: string;
  email: string;
  city: string;
  /** Manual seed rating until enough visit reviews exist. */
  rating: number | null;
  roles: PartnerRole[];
  category: string;
  partner_tier: PartnerTier;
  /** Average of last N visit experience ratings. */
  rolling_rating: number | null;
  rolling_rating_count: number;
  rolling_window: number;
  active: boolean;
  sort_order: number;
}

export interface ProductSupplierOffer {
  id: string;
  product_id: string;
  supplier_id: string;
  supplier_cost_inr: number;
  preferred: boolean;
  moq: number;
  lead_time_days: number;
  vendor_sku: string;
  active: boolean;
}

export interface SupplierDirectory {
  suppliers: Supplier[];
  offers: ProductSupplierOffer[];
}

export interface VendorSelectionContext {
  quantity?: number;
  jobCity?: string;
}

export interface SelectedVendorOffer {
  offer: ProductSupplierOffer;
  supplier: Supplier;
  reason: string;
}

export const PARTNER_CATEGORIES = [
  "Bathroom Safety",
  "Home Modifications",
  "Smart Home",
  "Medical Equipment",
  "Home Healthcare",
  "Nursing",
  "Physiotherapy",
  "Diagnostics",
  "Pharmacy",
  "Home Maintenance",
  "Property Management",
  "Hospitals",
  "Apartment Communities",
  "Other",
] as const;

export const MIN_RATINGS_FOR_ROLLING = 3;

/** Prefer rolling rating once enough family visit reviews exist. */
export function displayPartnerRating(partner: Supplier): number | null {
  if (
    partner.rolling_rating != null &&
    partner.rolling_rating_count >= MIN_RATINGS_FOR_ROLLING
  ) {
    return partner.rolling_rating;
  }
  if (partner.rating != null) return partner.rating;
  if (partner.rolling_rating != null && partner.rolling_rating_count > 0) {
    return partner.rolling_rating;
  }
  return null;
}

export function partnerRolesLabel(roles: PartnerRole[]): string {
  const set = new Set(roles);
  if (set.has("supplier") && set.has("installer")) return "Supplier + Installer";
  if (set.has("installer")) return "Installer";
  return "Supplier";
}

export function partnerTierLabel(tier: PartnerTier): string {
  switch (tier) {
    case "founding_platinum":
      return "Founding Platinum";
    case "gold":
      return "Gold Partner";
    case "silver":
      return "Silver Partner";
    default:
      return "—";
  }
}
