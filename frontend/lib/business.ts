import { api, downloadFileBlob, triggerBlobDownload } from "@/lib/api";

/** Phase 5B: business details, GST invoices, owner dashboard, monthly exports. Money is paise. */

export type BusinessDetails = {
  legal_name: string;
  trade_name: string;
  gstin: string;
  address: string;
  state_code: string;
  state_name: string;
  email: string;
  phone: string;
  invoice_prefix: string;
  default_sac: string;
  hsn_by_category: Record<string, string>;
  gst_registered: boolean;
  states: { code: string; name: string }[];
};

export type Invoice = {
  id: number;
  kind: "invoice" | "credit_note";
  doc_type: "tax_invoice" | "bill_of_supply";
  title: string;
  number: string;
  issued_at: string | null;
  elder_id: number;
  customer_name: string;
  source_type: string;
  source_id: string;
  original_number: string | null;
  taxable_paise: number;
  cgst_paise: number;
  sgst_paise: number;
  igst_paise: number;
  total_paise: number;
};

export type OwnerDashboard = {
  month: string;
  /** First month with any client ("YYYY-MM"); the picker starts here. */
  first_month?: string | null;
  as_of: string;
  gst_registered: boolean;
  cash: { this_month_paise: number; last_month_paise: number; billed_paise: number };
  dues: { total_paise: number; count: number; aging: { bucket: string; count: number; amount_paise: number }[] };
  pipeline: { status: string; count: number; amount_paise: number }[];
  margin: { orders: number; revenue_paise: number; cost_paise: number; margin_paise: number; margin_bp: number | null };
  visits: { planned: number; done: number; missed: number; cancelled: number };
  sos: { alerts: number; acknowledged: number; median_ack_minutes: number | null };
  reassessment: { active_clients: number; in_date: number; percent: number | null };
  utilisation: { caregivers: number; visit_hours: number; available_hours: number; percent: number | null };
  clients: { new: number; churned: number; active: number };
  satisfaction:
    | { available: false; message: string }
    | { available: true; ratings: number; average_rating: number | null; nps_responses: number; nps: number | null };
  exports: { key: string; label: string }[];
};

/** ₹ from paise, whole rupees unless there are paise. */
export function inr(paise: number): string {
  const neg = paise < 0;
  const abs = Math.abs(paise);
  const whole = Math.floor(abs / 100).toLocaleString("en-IN");
  const frac = abs % 100;
  return `${neg ? "-" : ""}₹${whole}${frac ? `.${String(frac).padStart(2, "0")}` : ""}`;
}

export const getBusinessDetails = () => api<BusinessDetails>("/api/v1/business/details");

export const saveBusinessDetails = (body: Partial<BusinessDetails>) =>
  api<BusinessDetails>("/api/v1/business/details", { method: "PUT", body: JSON.stringify(body) });

export const listInvoices = (elderId?: number) =>
  api<{ gst_registered: boolean; invoices: Invoice[] }>(
    `/api/v1/business/invoices${elderId ? `?elder_id=${elderId}` : ""}`,
  );

export const getOwnerDashboard = (month: string) =>
  api<OwnerDashboard>(`/api/v1/business/owner-dashboard?month=${encodeURIComponent(month)}`);

const fileName = (number: string) => `${number.replace(/\//g, "-")}.pdf`;

export async function downloadInvoicePdf(inv: Pick<Invoice, "id" | "number">, family = false) {
  const path = family
    ? `/api/v1/home-safety/family/invoices/${inv.id}/pdf`
    : `/api/v1/business/invoices/${inv.id}/pdf`;
  triggerBlobDownload(await downloadFileBlob(path), fileName(inv.number));
}

export const listFamilyInvoices = () => api<Invoice[]>("/api/v1/home-safety/family/invoices");

export async function downloadExport(kind: string, month: string) {
  const blob = await downloadFileBlob(`/api/v1/business/exports/${kind}.csv?month=${encodeURIComponent(month)}`);
  triggerBlobDownload(blob, `kushalaya-${kind}-${month}.csv`);
}

/** This month in IST, as YYYY-MM. */
export function currentMonthIST(): string {
  const d = new Date(Date.now() + 330 * 60_000);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}
