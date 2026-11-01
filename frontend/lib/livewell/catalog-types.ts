import type { CatalogCategoryType, ProductCategoryPrefix } from "./catalog-product-categories";

export interface CatalogProductImage {
  document_id: number;
  url?: string;
  supplier_id?: string | null;
  photo_kind?: "generic" | "vendor" | string;
}

export interface CatalogProduct {
  id: string;
  /** Display SKU e.g. BTH-001 */
  product_code?: string;
  name: string;
  short_description: string;
  details: string;
  /** Human category label (Bathroom Safety, etc.) */
  category: string;
  category_prefix?: ProductCategoryPrefix | string;
  price_inr: number | null;
  price_label: string;
  sort_order: number;
  image_ids?: number[];
  image_urls?: string[];
  /** Per-image metadata (generic vs vendor-linked). */
  images?: CatalogProductImage[];
  /** @deprecated First image — use image_urls */
  image_id?: number | null;
  /** @deprecated First image — use image_urls */
  image_url?: string | null;
  /** Solution-to-product catalog (v1.0) */
  purpose?: string;
  options?: string[];
  material?: string;
  installation_type?: string;
  contractor_type?: string;
  install_time?: string;
  product_cost?: string;
  installed_price?: string;
  life_years?: number | null;
  maintenance_schedule?: string;
  assessment_findings?: string[];
  safety_improvement?: number;
  /** Linked LiveWell solution library ids (LW-HS-BTH-001, …) */
  solution_ids?: string[];
}

export interface ServicePackage {
  id: string;
  name: string;
  tagline: string;
  description: string;
  price_inr: number | null;
  price_label: string;
  highlight: boolean;
  product_ids: string[];
  sort_order: number;
}

export interface SafetyCatalog {
  products: CatalogProduct[];
  packages: ServicePackage[];
  /** Admin-managed catalog types (SVC, BTH, …). Seeded from factory prefixes when empty. */
  category_types?: CatalogCategoryType[];
}
