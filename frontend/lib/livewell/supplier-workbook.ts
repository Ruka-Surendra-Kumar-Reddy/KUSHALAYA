import type { SupplierDirectory } from "./supplier-types";
import { normalizeSupplierDirectory } from "./suppliers";
import { publicBrandName } from "@/lib/public-brand";

/** Filename-safe brand prefix for exported workbook bundles (e.g. `KushAlaya_Suppliers.json`). */
export function supplierWorkbookFilePrefix(): string {
  return `${publicBrandName().replace(/[^A-Za-z0-9]+/g, "")}_Suppliers`;
}

/** Master workbook bundle (Suppliers + ProductSuppliers sheets). */
export interface SupplierWorkbookBundle {
  version: 1;
  exportedAt: string;
  Suppliers: SupplierWorkbookRow[];
  ProductSuppliers: ProductSupplierWorkbookRow[];
}

export interface SupplierWorkbookRow {
  SupplierID: string;
  Name: string;
  Contact: string;
  Phone: string;
  Email: string;
  City: string;
  Rating: string;
  Active: string;
  SortOrder: string;
}

export interface ProductSupplierWorkbookRow {
  ProductID: string;
  SupplierID: string;
  SupplierCostINR: string;
  Preferred: string;
  MOQ: string;
  LeadTimeDays: string;
  VendorSKU: string;
  Active: string;
}

const SUPPLIERS_HEADERS: (keyof SupplierWorkbookRow)[] = [
  "SupplierID",
  "Name",
  "Contact",
  "Phone",
  "Email",
  "City",
  "Rating",
  "Active",
  "SortOrder",
];

const OFFERS_HEADERS: (keyof ProductSupplierWorkbookRow)[] = [
  "ProductID",
  "SupplierID",
  "SupplierCostINR",
  "Preferred",
  "MOQ",
  "LeadTimeDays",
  "VendorSKU",
  "Active",
];

function yesNo(value: boolean): string {
  return value ? "Yes" : "No";
}

function parseYesNo(value: string | undefined): boolean {
  const v = (value ?? "").trim().toLowerCase();
  return v === "yes" || v === "y" || v === "true" || v === "1";
}

export function directoryToWorkbookBundle(directory: SupplierDirectory): SupplierWorkbookBundle {
  const normalized = normalizeSupplierDirectory(directory);
  return {
    version: 1,
    exportedAt: new Date().toISOString(),
    Suppliers: normalized.suppliers.map((s) => ({
      SupplierID: s.id,
      Name: s.name,
      Contact: s.contact,
      Phone: s.phone,
      Email: s.email,
      City: s.city,
      Rating: s.rating != null ? String(s.rating) : "",
      Active: yesNo(s.active),
      SortOrder: String(s.sort_order),
    })),
    ProductSuppliers: normalized.offers.map((o) => ({
      ProductID: o.product_id,
      SupplierID: o.supplier_id,
      SupplierCostINR: String(o.supplier_cost_inr),
      Preferred: yesNo(o.preferred),
      MOQ: String(o.moq),
      LeadTimeDays: String(o.lead_time_days),
      VendorSKU: o.vendor_sku,
      Active: yesNo(o.active),
    })),
  };
}

export function workbookBundleToDirectory(bundle: SupplierWorkbookBundle): SupplierDirectory {
  return normalizeSupplierDirectory({
    suppliers: bundle.Suppliers.map((row) => ({
      id: row.SupplierID.trim(),
      name: row.Name.trim(),
      contact: row.Contact.trim(),
      phone: row.Phone.trim(),
      email: row.Email.trim(),
      city: row.City.trim(),
      rating: row.Rating.trim() ? Number(row.Rating) : null,
      active: parseYesNo(row.Active),
      sort_order: Number(row.SortOrder) || 0,
    })),
    offers: bundle.ProductSuppliers.map((row) => ({
      id: `offer_${row.ProductID.trim()}_${row.SupplierID.trim()}`,
      product_id: row.ProductID.trim(),
      supplier_id: row.SupplierID.trim(),
      supplier_cost_inr: Number(row.SupplierCostINR) || 0,
      preferred: parseYesNo(row.Preferred),
      moq: Number(row.MOQ) || 1,
      lead_time_days: Number(row.LeadTimeDays) || 0,
      vendor_sku: row.VendorSKU.trim(),
      active: parseYesNo(row.Active),
    })),
  });
}

export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    const next = text[i + 1];
    if (inQuotes) {
      if (ch === '"' && next === '"') {
        cell += '"';
        i++;
      } else if (ch === '"') {
        inQuotes = false;
      } else {
        cell += ch;
      }
      continue;
    }
    if (ch === '"') {
      inQuotes = true;
      continue;
    }
    if (ch === ",") {
      row.push(cell);
      cell = "";
      continue;
    }
    if (ch === "\n" || (ch === "\r" && next === "\n")) {
      row.push(cell);
      if (row.some((c) => c.trim())) rows.push(row);
      row = [];
      cell = "";
      if (ch === "\r") i++;
      continue;
    }
    if (ch === "\r") {
      row.push(cell);
      if (row.some((c) => c.trim())) rows.push(row);
      row = [];
      cell = "";
      continue;
    }
    cell += ch;
  }
  row.push(cell);
  if (row.some((c) => c.trim())) rows.push(row);
  return rows;
}

function rowsToObjects<T extends object>(
  rows: string[][],
  headers: readonly (keyof T & string)[],
): T[] {
  if (!rows.length) return [];
  const headerRow = rows[0].map((h) => h.trim());
  const start = headers.every((h, i) => headerRow[i]?.toLowerCase() === String(h).toLowerCase())
    ? 1
    : 0;
  const out: T[] = [];
  for (const row of rows.slice(start)) {
    const obj = {} as T;
    let empty = true;
    for (let i = 0; i < headers.length; i++) {
      const key = headers[i];
      const value = (row[i] ?? "").trim();
      (obj as Record<string, string>)[key] = value;
      if (value) empty = false;
    }
    if (!empty) out.push(obj);
  }
  return out;
}

export function parseSuppliersCsv(text: string): SupplierWorkbookRow[] {
  return rowsToObjects<SupplierWorkbookRow>(parseCsv(text), SUPPLIERS_HEADERS);
}

export function parseProductSuppliersCsv(text: string): ProductSupplierWorkbookRow[] {
  return rowsToObjects<ProductSupplierWorkbookRow>(parseCsv(text), OFFERS_HEADERS);
}

export function suppliersToCsv(rows: SupplierWorkbookRow[]): string {
  const lines = [SUPPLIERS_HEADERS.join(",")];
  for (const row of rows) {
    lines.push(SUPPLIERS_HEADERS.map((h) => csvCell(row[h])).join(","));
  }
  return lines.join("\n");
}

export function productSuppliersToCsv(rows: ProductSupplierWorkbookRow[]): string {
  const lines = [OFFERS_HEADERS.join(",")];
  for (const row of rows) {
    lines.push(OFFERS_HEADERS.map((h) => csvCell(row[h])).join(","));
  }
  return lines.join("\n");
}

function csvCell(value: string): string {
  if (/[",\n]/.test(value)) return `"${value.replace(/"/g, '""')}"`;
  return value;
}

export function parseSupplierWorkbookFile(
  filename: string,
  text: string,
): SupplierDirectory {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".json")) {
    const raw = JSON.parse(text) as SupplierWorkbookBundle;
    if (!raw.Suppliers || !raw.ProductSuppliers) {
      throw new Error("JSON workbook must include Suppliers and ProductSuppliers arrays.");
    }
    return workbookBundleToDirectory(raw);
  }
  if (lower.includes("productsupplier") || lower.includes("product_supplier")) {
    return workbookBundleToDirectory({
      version: 1,
      exportedAt: new Date().toISOString(),
      Suppliers: [],
      ProductSuppliers: parseProductSuppliersCsv(text),
    });
  }
  if (lower.includes("supplier") && !lower.includes("product")) {
    return workbookBundleToDirectory({
      version: 1,
      exportedAt: new Date().toISOString(),
      Suppliers: parseSuppliersCsv(text),
      ProductSuppliers: [],
    });
  }
  const rows = parseCsv(text);
  const header = rows[0]?.map((h) => h.trim().toLowerCase()) ?? [];
  if (header.includes("supplierid") && header.includes("name")) {
    return workbookBundleToDirectory({
      version: 1,
      exportedAt: new Date().toISOString(),
      Suppliers: parseSuppliersCsv(text),
      ProductSuppliers: [],
    });
  }
  if (header.includes("productid") && header.includes("suppliercostinr")) {
    return workbookBundleToDirectory({
      version: 1,
      exportedAt: new Date().toISOString(),
      Suppliers: [],
      ProductSuppliers: parseProductSuppliersCsv(text),
    });
  }
  throw new Error("Unrecognized workbook format — use .json bundle or Suppliers/ProductSuppliers CSV.");
}

export function downloadTextFile(filename: string, content: string, mime = "text/csv"): void {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function exportSupplierWorkbook(directory: SupplierDirectory): void {
  const bundle = directoryToWorkbookBundle(directory);
  downloadTextFile(
    `${supplierWorkbookFilePrefix()}_${bundle.exportedAt.slice(0, 10)}.json`,
    JSON.stringify(bundle, null, 2),
    "application/json",
  );
  downloadTextFile("07_Suppliers.csv", suppliersToCsv(bundle.Suppliers));
  downloadTextFile("08_ProductSuppliers.csv", productSuppliersToCsv(bundle.ProductSuppliers));
}
