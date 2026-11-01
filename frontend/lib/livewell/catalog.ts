import type { CatalogProduct, SafetyCatalog, ServicePackage } from "./catalog-types";
import { DEFAULT_SAFETY_CATALOG } from "./catalog-defaults";
import {
  PRODUCT_CATEGORY_ORDER,
  defaultCatalogCategoryTypes,
  type CatalogCategoryType,
} from "./catalog-product-categories";
import { readLocalStorageWithLegacy, removeLocalStorageKeys } from "./legacyStorage";

export type { CatalogProduct, SafetyCatalog, ServicePackage } from "./catalog-types";
export {
  PRODUCT_CATEGORY_META,
  PRODUCT_CATEGORY_ORDER,
  SERVICE_CATEGORY_PREFIXES,
  categoryLabelFromPrefix,
  defaultCatalogCategoryTypes,
  type CatalogCategoryType,
} from "./catalog-product-categories";

/** Group key for catalog admin lists. */
export function catalogProductGroupKey(product: CatalogProduct): string {
  const prefix = product.category_prefix?.trim();
  if (prefix && prefix !== "OTHER") {
    return prefix;
  }
  const category = product.category?.trim();
  if (category) return category;
  return "OTHER";
}

export function groupCatalogProductsByPrefix(
  products: CatalogProduct[],
  typeOrder: string[] = PRODUCT_CATEGORY_ORDER as unknown as string[],
): { prefix: string; products: CatalogProduct[] }[] {
  const map = new Map<string, CatalogProduct[]>();
  for (const p of products) {
    const key = catalogProductGroupKey(p);
    const list = map.get(key) ?? [];
    list.push(p);
    map.set(key, list);
  }

  const known = new Set(typeOrder);
  const customKeys = [...map.keys()]
    .filter((k) => !known.has(k) && k !== "OTHER")
    .sort((a, b) => a.localeCompare(b));

  const orderedKeys = [
    ...typeOrder.filter((k) => map.has(k)),
    ...(map.has("OTHER") ? (["OTHER"] as const) : []),
    ...customKeys,
  ];

  return orderedKeys.map((prefix) => ({ prefix, products: map.get(prefix)! }));
}
export { productsForSolution, SEEDED_CATALOG_PRODUCTS } from "./catalog-product-seed";

const STORAGE_KEY = "safehome_home_safety_catalog_v2";
const LEGACY_STORAGE_KEYS = [
  "eldercare_home_safety_catalog_v2",
  "eldercare_home_safety_catalog_v1",
];

const defaultById = new Map(
  DEFAULT_SAFETY_CATALOG.products.map((p) => [p.id, p] as const),
);

function normalizeProduct(raw: CatalogProduct, index: number): CatalogProduct {
  const prefix = raw.category_prefix?.trim() || undefined;
  return {
    ...raw,
    product_code: raw.product_code?.trim() || undefined,
    name: raw.name?.trim() ?? "",
    short_description: raw.short_description?.trim() ?? "",
    details: raw.details?.trim() ?? "",
    category: raw.category?.trim() || "General",
    category_prefix: prefix,
    price_label: raw.price_label?.trim() || "Quote",
    sort_order: raw.sort_order ?? index,
    image_ids: raw.image_ids ?? (raw.image_id != null ? [raw.image_id] : []),
    image_url: raw.image_url ?? null,
    image_urls: raw.image_urls ?? [],
    purpose: raw.purpose?.trim() ?? "",
    options: (raw.options ?? []).map((o) => o.trim()).filter(Boolean),
    material: raw.material?.trim() ?? "",
    installation_type: raw.installation_type?.trim() ?? "",
    contractor_type: raw.contractor_type?.trim() ?? "",
    install_time: raw.install_time?.trim() ?? "",
    product_cost: raw.product_cost?.trim() ?? "",
    installed_price: raw.installed_price?.trim() ?? "",
    life_years: raw.life_years ?? null,
    maintenance_schedule: raw.maintenance_schedule?.trim() ?? "",
    assessment_findings: (raw.assessment_findings ?? []).map((f) => f.trim()).filter(Boolean),
    safety_improvement: Math.max(0, Number(raw.safety_improvement) || 0),
    solution_ids: [...new Set((raw.solution_ids ?? []).filter(Boolean))],
  };
}

/** Backfill spec fields from factory defaults when loading older saved catalogs. */
function mergeProductsFromDefaults(products: CatalogProduct[]): CatalogProduct[] {
  return products.map((p) => {
    const def = defaultById.get(p.id);
    if (!def) return p;
    return {
      ...def,
      ...p,
      solution_ids: p.solution_ids?.length ? p.solution_ids : def.solution_ids,
      assessment_findings: p.assessment_findings?.length
        ? p.assessment_findings
        : def.assessment_findings,
      product_code: p.product_code || def.product_code,
      category_prefix: p.category_prefix || def.category_prefix,
      options: p.options?.length ? p.options : def.options,
    };
  });
}

export function resolveCatalogCategoryTypes(catalog: SafetyCatalog): CatalogCategoryType[] {
  const raw = catalog.category_types ?? [];
  if (raw.length > 0) {
    return [...raw]
      .filter((t) => t.prefix?.trim())
      .sort((a, b) => a.sort - b.sort || a.prefix.localeCompare(b.prefix));
  }
  const defaults = defaultCatalogCategoryTypes();
  const present = new Set(
    catalog.products.map((p) => (p.category_prefix || "").trim()).filter(Boolean),
  );
  const extra = [...present]
    .filter((p) => !defaults.some((t) => t.prefix === p))
    .sort()
    .map((prefix, i) => ({
      prefix,
      label: prefix,
      kind: "product" as const,
      sort: 100 + i,
      active: true,
    }));
  return [...defaults, ...extra];
}

export function nextProductCode(prefix: string, products: CatalogProduct[]): string {
  const re = new RegExp(`^${prefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}-(\\d+)$`, "i");
  let max = 0;
  for (const product of products) {
    const match = (product.product_code || "").trim().match(re);
    if (match) max = Math.max(max, Number(match[1]));
  }
  return `${prefix}-${String(max + 1).padStart(3, "0")}`;
}

export function catalogTypeOrder(catalog: SafetyCatalog): string[] {
  return resolveCatalogCategoryTypes(catalog)
    .filter((t) => t.active !== false)
    .map((t) => t.prefix);
}

export function normalizeCatalog(raw: SafetyCatalog): SafetyCatalog {
  const products = (raw.products ?? [])
    .filter((p) => p.id && p.name.trim())
    .map((p, i) => normalizeProduct(p, i))
    .sort((a, b) => a.sort_order - b.sort_order);

  const merged =
    products.some((p) => defaultById.has(p.id)) || products.length === 0
      ? mergeProductsFromDefaults(products)
      : products;

  const validIds = new Set(merged.map((p) => p.id));
  const packages = (raw.packages ?? [])
    .filter((p) => p.id && p.name.trim())
    .map((p) => ({
      ...p,
      product_ids: (p.product_ids ?? []).filter((id) => validIds.has(id)),
      sort_order: p.sort_order ?? 0,
    }))
    .sort((a, b) => a.sort_order - b.sort_order);

  return {
    products: merged,
    packages,
    category_types: resolveCatalogCategoryTypes({
      products: merged,
      packages,
      category_types: raw.category_types,
    }),
  };
}

/** Trim text fields before persisting to the server. */
export function trimCatalogForSave(catalog: SafetyCatalog): SafetyCatalog {
  return normalizeCatalog({
    products: catalog.products.map((p) => ({
      ...p,
      name: p.name.trim(),
      short_description: p.short_description.trim(),
      details: p.details.trim(),
      category: p.category.trim(),
    })),
    packages: catalog.packages.map((p) => ({
      ...p,
      name: p.name.trim(),
      tagline: p.tagline.trim(),
      description: p.description.trim(),
    })),
    category_types: catalog.category_types,
  });
}

export function getLocalCatalog(): SafetyCatalog {
  if (typeof window === "undefined") {
    return { products: [], packages: [] };
  }
  try {
    const raw = readLocalStorageWithLegacy(STORAGE_KEY, LEGACY_STORAGE_KEYS);
    if (!raw) return { products: [], packages: [] };
    return normalizeCatalog(JSON.parse(raw) as SafetyCatalog);
  } catch {
    return { products: [], packages: [] };
  }
}

export function saveLocalCatalog(catalog: SafetyCatalog): SafetyCatalog {
  const normalized = normalizeCatalog(catalog);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
  removeLocalStorageKeys(...LEGACY_STORAGE_KEYS);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("home-safety-catalog-updated"));
  }
  return normalized;
}

export function resetLocalCatalog(): SafetyCatalog {
  removeLocalStorageKeys(STORAGE_KEY, ...LEGACY_STORAGE_KEYS);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("home-safety-catalog-updated"));
  }
  return DEFAULT_SAFETY_CATALOG;
}

/**
 * Apply factory text/pricing defaults while keeping existing product photos
 * (and solution links when the default row omits them).
 */
export function resetCatalogPreserveImages(previous: SafetyCatalog): SafetyCatalog {
  const prevById = new Map(previous.products.map((p) => [p.id, p]));
  const products = DEFAULT_SAFETY_CATALOG.products.map((p) => {
    const prev = prevById.get(p.id);
    if (!prev) return { ...p };
    const image_ids = prev.image_ids?.length ? [...prev.image_ids] : [...(p.image_ids ?? [])];
    const image_urls = prev.image_urls?.length ? [...prev.image_urls] : [...(p.image_urls ?? [])];
    const images = prev.images?.length ? [...prev.images] : [...(p.images ?? [])];
    const solution_ids =
      p.solution_ids?.length ? [...p.solution_ids] : [...(prev.solution_ids ?? [])];
    return {
      ...p,
      image_ids,
      image_urls,
      images,
      image_id: image_ids[0] ?? null,
      image_url: image_urls[0] ?? null,
      solution_ids,
    };
  });
  const next = normalizeCatalog({
    products,
    packages: DEFAULT_SAFETY_CATALOG.packages.map((pkg) => ({ ...pkg })),
    category_types: previous.category_types?.length
      ? previous.category_types
      : defaultCatalogCategoryTypes(),
  });
  if (typeof window !== "undefined") {
    return saveLocalCatalog(next);
  }
  return next;
}

const LEGACY_LABOR_COPY_RE =
  /billed separately|products extra|\(labor\)|install labor|project \(labor\)|labor \+ product/i;

/** True when copy still describes labor-only / products-extra pricing. */
export function hasLegacyLaborCopy(
  product: Pick<
    CatalogProduct,
    "name" | "short_description" | "price_label" | "details" | "purpose"
  >,
): boolean {
  return LEGACY_LABOR_COPY_RE.test(
    [product.name, product.short_description, product.price_label, product.details, product.purpose]
      .filter(Boolean)
      .join(" "),
  );
}

/**
 * Overlay factory name/pricing copy onto live catalog rows (keeps photos).
 * Only repairs legacy labor-only / "billed separately" copy. Product and package
 * content otherwise comes from the master spreadsheet (via API / synced defaults).
 */
export function withFactoryMarketingCopy(catalog: SafetyCatalog): SafetyCatalog {
  const productDefaults = new Map(DEFAULT_SAFETY_CATALOG.products.map((p) => [p.id, p]));
  const packageDefaults = new Map(DEFAULT_SAFETY_CATALOG.packages.map((p) => [p.id, p]));
  const pkgLegacy =
    /billed separately|billed separately or bundled|partner-rate/i;

  const products = catalog.products.map((p) => {
    const d = productDefaults.get(p.id);
    if (!d || !hasLegacyLaborCopy(p)) return p;
    return {
      ...p,
      name: d.name,
      short_description: d.short_description,
      details: d.details || p.details,
      purpose: d.purpose || p.purpose,
      price_label: d.price_label,
      price_inr: d.price_inr ?? p.price_inr,
      installed_price: d.installed_price || p.installed_price,
      product_cost: d.product_cost || p.product_cost,
    };
  });

  const packages = catalog.packages.map((pkg) => {
    const d = packageDefaults.get(pkg.id);
    if (!d || !pkgLegacy.test(pkg.description || "")) return pkg;
    return {
      ...pkg,
      name: d.name,
      tagline: d.tagline,
      description: d.description,
      price_label: d.price_label,
      price_inr: d.price_inr ?? pkg.price_inr,
    };
  });

  return normalizeCatalog({ products, packages });
}

export function newProductId(name: string): string {
  const base = name.toLowerCase().replace(/[^a-z0-9]+/g, "_").slice(0, 20) || "product";
  return `prod_${base}_${Date.now().toString(36)}`;
}

export function newPackageId(name: string): string {
  const base = name.toLowerCase().replace(/[^a-z0-9]+/g, "_").slice(0, 20) || "package";
  return `pkg_${base}_${Date.now().toString(36)}`;
}

export function formatInr(amount: number | null, label: string): string {
  if (amount == null) return label || "Quote on visit";
  const formatted = new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(amount);
  return label ? `${label} ${formatted}` : formatted;
}

/** Midpoint of a seeded installed-price range e.g. "₹1,200–₹1,800". */
export function parseInstalledPriceRange(range: string): number | null {
  const nums = range.match(/[\d,]+/g);
  if (!nums?.length) return null;
  const values = nums.map((n) => Number(n.replace(/,/g, ""))).filter((n) => !Number.isNaN(n));
  if (!values.length) return null;
  return Math.round(values.reduce((a, b) => a + b, 0) / values.length);
}

export function productUnitPriceInr(product: CatalogProduct): number | null {
  if (product.price_inr != null && product.price_inr > 0) return product.price_inr;
  if (product.installed_price?.trim()) {
    return parseInstalledPriceRange(product.installed_price);
  }
  if (product.product_cost?.trim()) {
    return parseInstalledPriceRange(product.product_cost);
  }
  return null;
}

/**
 * True when catalog sell price already includes professional install labor
 * (so the quote engine should not add solution labor hours again).
 * Hardware "Installed …" SKUs include labor; visit/clinical fees do not.
 */
export function catalogPriceIncludesInstallLabor(product: CatalogProduct): boolean {
  const label = (product.price_label || "").toLowerCase().trim();
  if (!label) return false;
  if (
    label.includes("per visit") ||
    label.includes("per day") ||
    label.includes("per hour") ||
    label.includes("per session") ||
    label.includes("per trip") ||
    label.includes("per month") ||
    label.includes("one-time") ||
    label.includes("setup") ||
    label.includes("per test") ||
    label.includes("per treatment") ||
    label.includes("per job") ||
    label.includes("per unit") ||
    label.includes("% of project")
  ) {
    return false;
  }
  if (label.includes("installed")) return true;
  if (label.includes("product + labor") || label.includes("product + labour")) {
    return true;
  }
  return false;
}

export function productsForPackage(
  catalog: SafetyCatalog,
  pkg: ServicePackage,
): CatalogProduct[] {
  const map = new Map(catalog.products.map((p) => [p.id, p]));
  return pkg.product_ids.map((id) => map.get(id)).filter(Boolean) as CatalogProduct[];
}

export function productsByCategoryPrefix(catalog: SafetyCatalog): Map<string, CatalogProduct[]> {
  const map = new Map<string, CatalogProduct[]>();
  for (const { prefix, products } of groupCatalogProductsByPrefix(
    catalog.products,
    catalogTypeOrder(catalog),
  )) {
    map.set(prefix, products);
  }
  return map;
}
