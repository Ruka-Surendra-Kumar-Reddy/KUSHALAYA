import type { ProductQuoteDraft } from "./product-recommendations";
import type { SafeHomePurchaseOrder, PurchaseOrderLine } from "./procurement-types";
import { selectVendorOffer } from "./supplier-selection";
import type { SupplierDirectory, VendorSelectionContext } from "./supplier-types";
import { publicBrandName } from "@/lib/public-brand";

export function newPurchaseOrderId(assessmentId: string): string {
  return `po-${assessmentId}-${Date.now().toString(36)}`;
}

export function buildPurchaseOrder(
  assessmentId: string,
  draft: ProductQuoteDraft,
  suppliers: SupplierDirectory,
  context: VendorSelectionContext = {},
  existing?: SafeHomePurchaseOrder | null,
): SafeHomePurchaseOrder {
  const now = new Date().toISOString();
  const overrides = new Map(
    (existing?.lines ?? []).map((line) => [line.product_id, line] as const),
  );

  const lines: PurchaseOrderLine[] = draft.items.map((item) => {
    const override = overrides.get(item.product.id);
    if (override?.supplier_id) {
      const supplier = suppliers.suppliers.find(
        (s) => s.id === override.supplier_id && s.active,
      );
      const offer = suppliers.offers.find(
        (o) =>
          o.product_id === item.product.id &&
          o.supplier_id === override.supplier_id &&
          o.active,
      );
      if (supplier) {
        return {
          product_id: item.product.id,
          product_code: item.product.product_code,
          product_name: item.product.name,
          quantity: item.quantity,
          sell_unit_price_inr: item.unitPriceInr,
          supplier_id: supplier.id,
          supplier_name: supplier.name,
          supplier_cost_inr: offer?.supplier_cost_inr ?? override.supplier_cost_inr,
          vendor_sku: offer?.vendor_sku ?? override.vendor_sku,
          selection_reason: "manual override",
          lead_time_days: offer?.lead_time_days ?? override.lead_time_days,
          moq: offer?.moq ?? override.moq,
        };
      }
    }

    const selected = selectVendorOffer(suppliers, item.product.id, {
      ...context,
      quantity: item.quantity,
    });
    if (!selected) {
      return {
        product_id: item.product.id,
        product_code: item.product.product_code,
        product_name: item.product.name,
        quantity: item.quantity,
        sell_unit_price_inr: item.unitPriceInr,
        supplier_id: "",
        supplier_name: "— unassigned —",
        supplier_cost_inr: 0,
        vendor_sku: "",
        selection_reason: "no eligible vendor",
        lead_time_days: 0,
        moq: 1,
      };
    }

    return {
      product_id: item.product.id,
      product_code: item.product.product_code,
      product_name: item.product.name,
      quantity: item.quantity,
      sell_unit_price_inr: item.unitPriceInr,
      supplier_id: selected.supplier.id,
      supplier_name: selected.supplier.name,
      supplier_cost_inr: selected.offer.supplier_cost_inr,
      vendor_sku: selected.offer.vendor_sku,
      selection_reason: selected.reason,
      lead_time_days: selected.offer.lead_time_days,
      moq: selected.offer.moq,
    };
  });

  return {
    id: existing?.id ?? newPurchaseOrderId(assessmentId),
    assessment_id: assessmentId,
    created_at: existing?.created_at ?? now,
    updated_at: now,
    status: existing?.status ?? "draft",
    job_city: context.jobCity ?? existing?.job_city,
    lines,
    notes: existing?.notes ?? "",
  };
}

export function purchaseOrderCostTotalInr(order: SafeHomePurchaseOrder): number {
  return order.lines.reduce(
    (sum, line) => sum + line.supplier_cost_inr * line.quantity,
    0,
  );
}

/** Stable key for quote ↔ PO line alignment (product + qty). */
export function quoteDraftLineKey(draft: ProductQuoteDraft): string {
  return draft.items.map((i) => `${i.product.id}:${i.quantity}`).join("|");
}

export function purchaseOrderLineKey(order: SafeHomePurchaseOrder): string {
  return order.lines.map((l) => `${l.product_id}:${l.quantity}`).join("|");
}

export function formatPurchaseOrderText(order: SafeHomePurchaseOrder): string {
  const lines: string[] = [
    `${publicBrandName().toUpperCase()} PURCHASE ORDER`,
    `PO: ${order.id}`,
    `Assessment: ${order.assessment_id}`,
    `Status: ${order.status}`,
    order.job_city ? `Job city: ${order.job_city}` : "",
    "",
    "LINE ITEMS",
  ].filter(Boolean);

  for (const line of order.lines) {
    const code = line.product_code ?? line.product_id;
    lines.push(
      `${code} — ${line.product_name} × ${line.quantity}`,
      `  Vendor: ${line.supplier_name} (${line.selection_reason})`,
      `  Vendor SKU: ${line.vendor_sku || "—"}`,
      `  Cost: ₹${(line.supplier_cost_inr * line.quantity).toLocaleString("en-IN")} (@ ₹${line.supplier_cost_inr.toLocaleString("en-IN")}/ea)`,
      `  Lead: ${line.lead_time_days} day(s) · MOQ ${line.moq}`,
      line.sell_unit_price_inr != null
        ? `  Sell ref: ₹${line.sell_unit_price_inr.toLocaleString("en-IN")}/ea`
        : "",
    );
  }

  lines.push(
    "",
    `Procurement total: ₹${purchaseOrderCostTotalInr(order).toLocaleString("en-IN")}`,
  );
  if (order.notes.trim()) {
    lines.push("", "Notes:", order.notes.trim());
  }
  return lines.filter(Boolean).join("\n");
}

export function purchaseOrderToCsv(order: SafeHomePurchaseOrder): string {
  const headers = [
    "ProductID",
    "ProductCode",
    "ProductName",
    "Qty",
    "SupplierID",
    "SupplierName",
    "SupplierCostINR",
    "VendorSKU",
    "LeadTimeDays",
    "MOQ",
    "SelectionReason",
    "SellUnitPriceINR",
  ];
  const rows = order.lines.map((line) =>
    [
      line.product_id,
      line.product_code ?? "",
      line.product_name,
      String(line.quantity),
      line.supplier_id,
      line.supplier_name,
      String(line.supplier_cost_inr),
      line.vendor_sku,
      String(line.lead_time_days),
      String(line.moq),
      line.selection_reason,
      line.sell_unit_price_inr != null ? String(line.sell_unit_price_inr) : "",
    ]
      .map(csvCell)
      .join(","),
  );
  return [headers.join(","), ...rows].join("\n");
}

function csvCell(value: string): string {
  if (/[",\n]/.test(value)) return `"${value.replace(/"/g, '""')}"`;
  return value;
}
