import { api, downloadFileBlob, postFormData, triggerBlobDownload } from "@/lib/api";
import { fetchAdminCatalog } from "./catalogApi";
import { fetchAdminPricing } from "./pricingApi";
import { fetchAdminRubric } from "./rubricApi";
import { fetchAdminSolutions } from "./solutionApi";
import { fetchAdminSuppliers } from "./supplierApi";
import type { SafeHomePricingConfig } from "./pricing-types";

export interface MasterDataCatalogPhotoPreview {
  products_with_photos_before: number;
  products_with_photos_after: number;
  would_lose_photos: boolean;
}

export interface MasterDataFieldChange {
  entity: string;
  id: string;
  field: string;
  before?: unknown;
  after?: unknown;
  change_type: string;
}

export interface MasterDataFieldDiff {
  dirty: boolean;
  change_count: number;
  truncated?: boolean;
  by_entity?: Record<string, number>;
  changes: MasterDataFieldChange[];
}

export interface MasterDataImportResult {
  version_id: string;
  status: string;
  errors: string[];
  warnings: string[];
  diff: Record<string, Record<string, unknown>>;
  field_diff?: MasterDataFieldDiff | Record<string, unknown>;
  sheets_found: string[];
  entities: string[];
  workbook_meta?: Record<string, unknown>;
  catalog_photo_preview?: MasterDataCatalogPhotoPreview | null;
  staged_pricing?: SafeHomePricingConfig | null;
  live_pricing?: SafeHomePricingConfig | null;
  pricing_from_workbook?: boolean;
  pricing_edited_in_staging?: boolean;
}

export interface MasterDataConfigSummary {
  rubric_categories: number;
  rubric_questions: number;
  solutions: number;
  catalog_products: number;
  catalog_packages: number;
  products_with_photos: number;
  products_with_solution_links: number;
  pricing_keys: number;
  suppliers: number;
  supplier_offers: number;
}

export interface MasterDataVersionSummary {
  version_id: string | null;
  approved_at: string | null;
  approved_by: number | null;
  comments: string;
  applied: string[];
  snapshot_summary?: MasterDataConfigSummary | null;
  matches_current?: boolean;
  is_latest_import?: boolean;
  is_current_baseline?: boolean;
}

export interface MasterDataSyncStatus {
  has_baseline: boolean;
  upload_id: string | null;
  approved_at: string | null;
  exported_at: string | null;
  is_empty: boolean;
  requires_upload: boolean;
  dirty: boolean;
  drift: MasterDataFieldDiff;
  summary: MasterDataConfigSummary | Record<string, number>;
  message: string;
}

export async function exportMasterWorkbook(): Promise<void> {
  const blob = await downloadFileBlob("/api/v1/home-safety/master-data/export");
  triggerBlobDownload(blob, "Kushalaya_Configuration.xlsx");
}

/** Stages factory workbook for Approve — does not write live config until approved. */
export async function seedMasterDefaults(): Promise<MasterDataImportResult> {
  return api<MasterDataImportResult>("/api/v1/home-safety/master-data/seed-defaults", {
    method: "POST",
  });
}

export async function importMasterWorkbook(
  file: File,
  comments = "",
): Promise<MasterDataImportResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("comments", comments);
  return postFormData<MasterDataImportResult>("/api/v1/home-safety/master-data/import", form);
}

export async function approveMasterImport(
  versionId: string,
  opts?: { confirmCatalogPhotoLoss?: boolean },
): Promise<{ version_id: string; status: string; applied: string[]; upload_id?: string }> {
  return api("/api/v1/home-safety/master-data/import/approve", {
    method: "POST",
    body: JSON.stringify({
      version_id: versionId,
      confirm_catalog_photo_loss: opts?.confirmCatalogPhotoLoss ?? false,
    }),
  });
}

export async function saveStagedImportPricing(
  versionId: string,
  pricing: SafeHomePricingConfig,
): Promise<MasterDataImportResult> {
  return api<MasterDataImportResult>(
    `/api/v1/home-safety/master-data/import/${encodeURIComponent(versionId)}/pricing`,
    {
      method: "PUT",
      body: JSON.stringify({ pricing }),
    },
  );
}

export async function listMasterVersions(): Promise<MasterDataVersionSummary[]> {
  return api<MasterDataVersionSummary[]>("/api/v1/home-safety/master-data/versions");
}

export async function fetchMasterDataCurrentSummary(): Promise<MasterDataConfigSummary> {
  const res = await api<{ summary: MasterDataConfigSummary }>("/api/v1/home-safety/master-data/current");
  return res.summary;
}

export async function fetchMasterDataSyncStatus(): Promise<MasterDataSyncStatus> {
  return api<MasterDataSyncStatus>("/api/v1/home-safety/master-data/sync-status");
}

export function formatMasterDataSummary(s: MasterDataConfigSummary | Record<string, number>): string {
  const summary = s as MasterDataConfigSummary;
  return [
    `${summary.catalog_products ?? 0} products`,
    `${summary.catalog_packages ?? 0} packages`,
    `${summary.products_with_photos ?? 0} with photos`,
    `${summary.rubric_categories ?? 0} rubric categories`,
    `${summary.solutions ?? 0} solutions`,
  ].join(" · ");
}

export interface MasterDataRollbackResult {
  version_id: string;
  status: string;
  summary?: MasterDataConfigSummary;
  versions_removed?: number;
  sync?: MasterDataSyncStatus;
}

export async function rollbackMasterVersion(versionId: string): Promise<MasterDataRollbackResult> {
  return api<MasterDataRollbackResult>(
    `/api/v1/home-safety/master-data/rollback/${encodeURIComponent(versionId)}`,
    { method: "POST" },
  );
}

/** Pull all SafeHome config from server into localStorage caches after master import approve. */
export async function refreshHomeSafetyCaches(): Promise<void> {
  await Promise.all([
    fetchAdminRubric().catch(() => undefined),
    fetchAdminSolutions().catch(() => undefined),
    fetchAdminCatalog().catch(() => undefined),
    fetchAdminPricing().catch(() => undefined),
    fetchAdminSuppliers().catch(() => undefined),
  ]);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("home-safety-rubric-updated"));
    window.dispatchEvent(new CustomEvent("home-safety-master-sync-updated"));
  }
}
