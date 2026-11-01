import { api, getStoredAuth } from "@/lib/api";
import type { SafetyCatalog } from "./catalog-types";
import {
  getLocalCatalog,
  saveLocalCatalog,
  trimCatalogForSave,
  withFactoryMarketingCopy,
} from "./catalog";
import { DEFAULT_SAFETY_CATALOG } from "./catalog-defaults";
import { brandifyDeep } from "@/lib/brandify";

/**
 * Catalog rows come from the database, where names may still carry the
 * LiveWell360 authoring token (or a pre-rename seed). Rewrite once here so
 * every consumer — pickers, quotes, showcase — renders the configured brand.
 */
export async function fetchAdminCatalog(): Promise<SafetyCatalog> {
  const catalog = brandifyDeep(await api<SafetyCatalog>("/api/v1/home-safety/catalog"));
  saveLocalCatalog(catalog);
  return catalog;
}

export async function saveAdminCatalog(catalog: SafetyCatalog): Promise<SafetyCatalog> {
  const payload = trimCatalogForSave(catalog);
  const saved = brandifyDeep(
    await api<SafetyCatalog>("/api/v1/home-safety/catalog", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  );
  saveLocalCatalog(saved);
  return saved;
}

export function getCachedCatalog(): SafetyCatalog {
  return getLocalCatalog();
}

export async function fetchShowcaseCatalog(_tenantId?: number): Promise<SafetyCatalog> {
  const path = "/api/v1/home-safety/catalog/public";
  try {
    const { getApiUrl } = await import("@/lib/api");
    const res = await fetch(`${getApiUrl()}${path}`, { credentials: "omit" });
    if (!res.ok) {
      throw new Error(`Catalog fetch failed (${res.status})`);
    }
    return withFactoryMarketingCopy(brandifyDeep((await res.json()) as SafetyCatalog));
  } catch {
    if (getStoredAuth()?.access_token) {
      try {
        return withFactoryMarketingCopy(await fetchAdminCatalog());
      } catch {
        /* local fallback */
      }
    }
    const local = getLocalCatalog();
    if (local.products.length > 0) {
      return withFactoryMarketingCopy(local);
    }
    return DEFAULT_SAFETY_CATALOG;
  }
}
