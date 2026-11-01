/** SafeHome 360™ purchase order — procurement after customer quote. */

export type PurchaseOrderStatus = "draft" | "approved" | "ordered";

export interface PurchaseOrderLine {
  product_id: string;
  product_code?: string;
  product_name: string;
  quantity: number;
  /** Customer sell price (reference only — quote unchanged). */
  sell_unit_price_inr: number | null;
  supplier_id: string;
  supplier_name: string;
  supplier_cost_inr: number;
  vendor_sku: string;
  selection_reason: string;
  lead_time_days: number;
  moq: number;
}

export interface SafeHomePurchaseOrder {
  id: string;
  assessment_id: string;
  created_at: string;
  updated_at: string;
  status: PurchaseOrderStatus;
  job_city?: string;
  lines: PurchaseOrderLine[];
  notes: string;
}
