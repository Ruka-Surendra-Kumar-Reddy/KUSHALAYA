/** SafeHome 360™ Solution-to-Product catalog category prefixes (v1.0). */

import { withPublicBrand } from "@/lib/public-brand";

export type CatalogTypeKind = "service" | "product";

export type ProductCategoryPrefix =
  | "BTH"
  | "BED"
  | "LIV"
  | "EXT"
  | "KIT"
  | "HAL"
  | "BAL"
  | "SMT"
  | "EMG"
  | "WEL"
  | "MOB"
  | "SVC"
  | "HM"
  | "NUR"
  | "PHY"
  | "DX"
  | "PM"
  | "TRN"
  | "HLT";

export const PRODUCT_CATEGORY_META: Record<
  ProductCategoryPrefix,
  { label: string; sort: number }
> = {
  SVC: { label: withPublicBrand("KushAlaya Services"), sort: 0 },
  BTH: { label: "Bathroom Safety", sort: 1 },
  BED: { label: "Bedroom Safety", sort: 2 },
  LIV: { label: "Living Room", sort: 3 },
  EXT: { label: "Entry & Exterior", sort: 4 },
  HAL: { label: "Hallway Safety", sort: 5 },
  KIT: { label: "Kitchen Safety", sort: 6 },
  BAL: { label: "Balcony Safety", sort: 7 },
  MOB: { label: "Mobility", sort: 8 },
  SMT: { label: "Smart Home", sort: 9 },
  EMG: { label: "Emergency Safety", sort: 10 },
  WEL: { label: "Care & Wellness Services", sort: 11 },
  HM: { label: "Home Maintenance", sort: 12 },
  NUR: { label: "Nursing", sort: 13 },
  PHY: { label: "Physiotherapy", sort: 14 },
  DX: { label: "Doctor & Diagnostics", sort: 15 },
  PM: { label: "Property Management", sort: 16 },
  TRN: { label: "Transportation", sort: 17 },
  HLT: { label: "Health Monitoring", sort: 18 },
};

export const PRODUCT_CATEGORY_ORDER: ProductCategoryPrefix[] = [
  "SVC",
  "BTH",
  "BED",
  "LIV",
  "EXT",
  "HAL",
  "KIT",
  "BAL",
  "MOB",
  "SMT",
  "EMG",
  "WEL",
  "HM",
  "NUR",
  "PHY",
  "DX",
  "PM",
  "TRN",
  "HLT",
];

/** Catalog types that are sold as services (visits, care, membership-style SKUs). */
export const SERVICE_CATEGORY_PREFIXES: ReadonlySet<string> = new Set([
  "SVC",
  "WEL",
  "NUR",
  "PHY",
  "DX",
  "HM",
  "PM",
  "TRN",
]);

export type CatalogCategoryType = {
  prefix: string;
  label: string;
  kind: CatalogTypeKind;
  sort: number;
  active: boolean;
};

export function defaultCatalogCategoryTypes(): CatalogCategoryType[] {
  return PRODUCT_CATEGORY_ORDER.map((prefix, index) => ({
    prefix,
    label: PRODUCT_CATEGORY_META[prefix].label,
    kind: SERVICE_CATEGORY_PREFIXES.has(prefix) ? "service" : "product",
    sort: PRODUCT_CATEGORY_META[prefix].sort ?? index,
    active: true,
  }));
}

export function categoryLabelFromPrefix(prefix: string | undefined): string {
  if (!prefix) return "General";
  const meta = PRODUCT_CATEGORY_META[prefix as ProductCategoryPrefix];
  return meta?.label ?? prefix;
}
