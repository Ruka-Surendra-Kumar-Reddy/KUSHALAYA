import { getApiUrl, postFormData } from "@/lib/api";
import type { CatalogProduct } from "./catalog-types";
import type { SafetyCatalog } from "./catalog-types";

/** /api paths go to the API base (they 404 on the Next.js origin); the website's own
 * picture files (/marketing/products/…) stay on this site. */
function resolveImagePath(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return path.startsWith("/api/") ? `${getApiUrl()}${path}` : path;
}

/** Global catalog images — no tenant_id required. */
export function catalogImageUrl(documentId: number, _tenantId?: number): string {
  return resolveImagePath(`/api/v1/home-safety/catalog/public/images/${documentId}`);
}

/** All browser-loadable image URLs for a catalog product. */
export function catalogProductImageUrls(
  product: Pick<CatalogProduct, "image_urls" | "image_ids" | "image_url" | "image_id">,
  _tenantId?: number,
): string[] {
  if (product.image_urls?.length) {
    return product.image_urls.map(resolveImagePath);
  }
  if (product.image_ids?.length) {
    return product.image_ids.map((id) => catalogImageUrl(id));
  }
  if (product.image_url) {
    return [resolveImagePath(product.image_url)];
  }
  if (product.image_id != null) {
    return [catalogImageUrl(product.image_id)];
  }
  return [];
}

/** First product image URL, if any. */
export function catalogProductImageSrc(
  product: Pick<CatalogProduct, "image_urls" | "image_ids" | "image_url" | "image_id">,
  tenantId?: number,
): string | null {
  const urls = catalogProductImageUrls(product, tenantId);
  return urls[0] ?? null;
}

export async function uploadCatalogProductImage(
  productId: string,
  file: File,
  opts?: { supplier_id?: string | null },
): Promise<SafetyCatalog> {
  const form = new FormData();
  form.append("file", file, file.name);
  if (opts?.supplier_id) {
    form.append("supplier_id", opts.supplier_id);
  }
  return postFormData<SafetyCatalog>(
    `/api/v1/home-safety/catalog/products/${encodeURIComponent(productId)}/image`,
    form,
  );
}

export async function removeCatalogProductImage(
  productId: string,
  documentId: number,
): Promise<SafetyCatalog> {
  const { api } = await import("@/lib/api");
  return api<SafetyCatalog>(
    `/api/v1/home-safety/catalog/products/${encodeURIComponent(productId)}/images/${documentId}`,
    { method: "DELETE" },
  );
}

export async function removeAllCatalogProductImages(
  productId: string,
): Promise<SafetyCatalog> {
  const { api } = await import("@/lib/api");
  return api<SafetyCatalog>(
    `/api/v1/home-safety/catalog/products/${encodeURIComponent(productId)}/image`,
    { method: "DELETE" },
  );
}
