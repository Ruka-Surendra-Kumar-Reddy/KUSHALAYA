"use client";

import { useEffect, useRef } from "react";
import type { HomeSafetyAssessment } from "@/lib/livewell/assessment";
import { assessmentJobCity } from "@/lib/livewell/assessment";
import { formatInr } from "@/lib/livewell/catalog";
import {
  buildPurchaseOrder,
  formatPurchaseOrderText,
  purchaseOrderCostTotalInr,
  purchaseOrderLineKey,
  purchaseOrderToCsv,
  quoteDraftLineKey,
} from "@/lib/livewell/build-purchase-order";
import type { ProductQuoteDraft } from "@/lib/livewell/product-recommendations";
import type { SafeHomePurchaseOrder } from "@/lib/livewell/procurement-types";
import { downloadTextFile } from "@/lib/livewell/supplier-workbook";
import { offersForProduct } from "@/lib/livewell/suppliers";
import type { SupplierDirectory } from "@/lib/livewell/supplier-types";

export function ProcurementOrderPanel({
  assessment,
  draft,
  suppliers,
  purchaseOrder,
  onPurchaseOrderChange,
  onAction,
}: {
  assessment: HomeSafetyAssessment;
  draft: ProductQuoteDraft;
  suppliers: SupplierDirectory;
  purchaseOrder: SafeHomePurchaseOrder | null;
  onPurchaseOrderChange: (order: SafeHomePurchaseOrder | null) => void;
  onAction?: (message: string, error?: string) => void;
}) {
  const jobCity = assessmentJobCity(assessment);
  const order = purchaseOrder;
  const syncNoteRef = useRef(false);

  // Keep an existing PO aligned with the customer quote when solutions/products change.
  useEffect(() => {
    if (!order) return;
    if (!draft.items.length) {
      onPurchaseOrderChange(null);
      if (!syncNoteRef.current) {
        syncNoteRef.current = true;
        onAction?.("Purchase order cleared — no products on the current quote.");
      }
      return;
    }
    const draftKey = quoteDraftLineKey(draft);
    const poKey = purchaseOrderLineKey(order);
    if (draftKey === poKey) {
      syncNoteRef.current = false;
      return;
    }
    const built = buildPurchaseOrder(assessment.id, draft, suppliers, { jobCity }, order);
    onPurchaseOrderChange(built);
    if (!syncNoteRef.current) {
      syncNoteRef.current = true;
      onAction?.("Purchase order updated to match the customer quote.");
    }
  }, [
    assessment.id,
    draft,
    jobCity,
    onAction,
    onPurchaseOrderChange,
    order,
    suppliers,
  ]);

  if (!draft.items.length && !order) return null;

  function generatePo() {
    const built = buildPurchaseOrder(assessment.id, draft, suppliers, { jobCity });
    onPurchaseOrderChange(built);
    onAction?.("Purchase order draft generated with auto-selected vendors.");
  }

  function refreshVendors() {
    if (!order) return;
    const built = buildPurchaseOrder(assessment.id, draft, suppliers, { jobCity }, {
      ...order,
      lines: [],
    });
    onPurchaseOrderChange(built);
    onAction?.("Vendors re-selected from supplier rules.");
  }

  function updateLineSupplier(productId: string, supplierId: string) {
    if (!order) return;
    const supplier = suppliers.suppliers.find((s) => s.id === supplierId);
    const offer = suppliers.offers.find(
      (o) => o.product_id === productId && o.supplier_id === supplierId,
    );
    onPurchaseOrderChange({
      ...order,
      updated_at: new Date().toISOString(),
      lines: order.lines.map((line) =>
        line.product_id === productId
          ? {
              ...line,
              supplier_id: supplierId,
              supplier_name: supplier?.name ?? line.supplier_name,
              supplier_cost_inr: offer?.supplier_cost_inr ?? line.supplier_cost_inr,
              vendor_sku: offer?.vendor_sku ?? "",
              lead_time_days: offer?.lead_time_days ?? line.lead_time_days,
              moq: offer?.moq ?? line.moq,
              selection_reason: "manual override",
            }
          : line,
      ),
    });
  }

  function copyPo() {
    if (!order) return;
    const text = formatPurchaseOrderText(order);
    navigator.clipboard
      .writeText(text)
      .then(() => onAction?.("Purchase order copied."))
      .catch(() => onAction?.("", "Could not copy purchase order."));
  }

  function exportPoCsv() {
    if (!order) return;
    downloadTextFile(`PO_${order.id}.csv`, purchaseOrderToCsv(order));
    onAction?.("Purchase order CSV downloaded.");
  }

  return (
    <section className="card home-safety-section home-safety-procurement">
      <div className="home-safety-improvement-head">
        <h2>Purchase order</h2>
        {order ? (
          <p className="muted home-safety-improvement-score">
            Procurement total{" "}
            <strong>{formatInr(purchaseOrderCostTotalInr(order), "")}</strong>
            <span className="home-safety-improvement-gain"> · {order.status}</span>
          </p>
        ) : null}
      </div>

      <p className="muted home-safety-section-hint">
        After the customer quote, generate a PO with auto-selected vendors (preferred → lowest
        cost → lead time). When the quote products change, this PO updates automatically (manual
        vendor picks are kept for SKUs that remain).
      </p>

      <div className="home-safety-quote-actions">
        {!order ? (
          <button
            type="button"
            className="primary"
            onClick={generatePo}
            disabled={!draft.items.length}
          >
            Generate purchase order
          </button>
        ) : (
          <>
            <button type="button" className="secondary" onClick={refreshVendors}>
              Re-select vendors
            </button>
            <button type="button" className="primary" onClick={copyPo}>
              Copy PO
            </button>
            <button type="button" className="secondary" onClick={exportPoCsv}>
              Export CSV
            </button>
          </>
        )}
      </div>

      {order ? (
        <div className="home-safety-quote-table-wrap">
          <table className="data-table home-safety-quote-table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Product</th>
                <th>Vendor</th>
                <th>Cost</th>
                <th>Lead</th>
                <th>Sell ref</th>
              </tr>
            </thead>
            <tbody>
              {order.lines.map((line) => {
                const offers = offersForProduct(suppliers, line.product_id);
                return (
                  <tr key={line.product_id}>
                    <td>
                      <code>{line.product_code ?? "—"}</code>
                    </td>
                    <td>{line.product_name}</td>
                    <td>
                      <select
                        value={line.supplier_id}
                        onChange={(e) => updateLineSupplier(line.product_id, e.target.value)}
                      >
                        <option value="">— unassigned —</option>
                        {offers.map((offer) => {
                          const supplier = suppliers.suppliers.find(
                            (s) => s.id === offer.supplier_id,
                          );
                          return (
                            <option key={offer.id} value={offer.supplier_id}>
                              {supplier?.name ?? offer.supplier_id} (₹{offer.supplier_cost_inr})
                            </option>
                          );
                        })}
                      </select>
                      <div className="muted" style={{ fontSize: "0.8rem" }}>
                        {line.selection_reason}
                      </div>
                    </td>
                    <td>{formatInr(line.supplier_cost_inr * line.quantity, "")}</td>
                    <td>{line.lead_time_days}d</td>
                    <td className="muted">
                      {line.sell_unit_price_inr != null
                        ? formatInr(line.sell_unit_price_inr, "")
                        : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}

    </section>
  );
}
