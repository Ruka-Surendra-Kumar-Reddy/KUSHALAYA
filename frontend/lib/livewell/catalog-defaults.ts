import type { SafetyCatalog } from "./catalog-types";
import workbookCatalog from "./generated/catalog-from-workbook.json";

/**
 * Offline / factory fallback catalog.
 *
 * Source of truth: `backend/app/livewell/data/Kushalaya_Configuration.xlsx`
 * (sheets 05–06, 10–11). Regenerate this mirror after editing the workbook:
 *
 *   python backend/scripts/sync_catalog_defaults_from_workbook.py
 *
 * Do not hand-edit products/packages here.
 */
export const DEFAULT_SAFETY_CATALOG: SafetyCatalog = workbookCatalog as SafetyCatalog;
