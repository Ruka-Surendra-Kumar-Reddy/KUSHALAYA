import { api, downloadFileBlob, triggerBlobDownload } from "./api";

export type Visit = {
  id: number;
  assignment_id: number;
  elder_id: number;
  caregiver_id: number;
  elder_name?: string | null;
  caregiver_name?: string | null;
  scheduled_start: string;
  scheduled_end: string;
  status: string;
  attendance_record_id: number | null;
};

export type PayrollDeduction = {
  deduction_type: string;
  base_amount: number;
  rate: number | null;
  amount: number;
  notes: string | null;
};

export type PayrollCaregiverSummary = {
  caregiver_id: number;
  caregiver_name: string;
  hours: number;
  gross: number;
  deductions: PayrollDeduction[];
  total_deductions: number;
  net: number;
};

export type PayrollRun = {
  id: number;
  period_start: string;
  period_end: string;
  status: string;
  total_amount: number;
  total_deductions?: number;
  total_net?: number;
  lines: {
    caregiver_id: number;
    hours: number;
    hourly_rate: number;
    amount: number;
    description: string | null;
  }[];
  summaries?: PayrollCaregiverSummary[];
};

export type Invoice = {
  id: number;
  elder_id: number;
  invoice_number: string | null;
  period_start: string;
  period_end: string;
  status: string;
  subtotal: number;
  tax_rate: number;
  tax_amount: number;
  total_amount: number;
  amount_paid: number;
  due_date: string | null;
  issued_at: string | null;
  paid_at: string | null;
  lines: {
    description: string;
    hours: number;
    unit_price: number;
    amount: number;
  }[];
};

export type CollectionsSummary = {
  as_of: string;
  total_outstanding: number;
  overdue_count: number;
  buckets: Record<
    string,
    {
      invoice_id: number;
      invoice_number: string | null;
      elder_id: number;
      elder_name: string;
      due_date: string | null;
      total_amount: number;
      amount_paid: number;
      balance: number;
      status: string;
      days_overdue: number;
    }[]
  >;
};

export async function listVisits(params?: {
  from_date?: string;
  to_date?: string;
}): Promise<Visit[]> {
  const q = new URLSearchParams();
  if (params?.from_date) q.set("from_date", params.from_date);
  if (params?.to_date) q.set("to_date", params.to_date);
  const suffix = q.toString() ? `?${q}` : "";
  return api<Visit[]>(`/api/v1/scheduling/visits${suffix}`);
}

export async function generateSchedule(payload: {
  start_date: string;
  end_date: string;
}): Promise<{ created: number; skipped: number }> {
  return api("/api/v1/scheduling/generate", {
    method: "POST",
    body: JSON.stringify({
      ...payload,
      default_start_hour: 9,
      default_duration_hours: 4,
    }),
  });
}

export async function getScheduleCoverage(): Promise<{
  active_assignments: number;
  visits_scheduled: number;
  visits_completed: number;
  uncovered_assignments: number;
}> {
  return api("/api/v1/scheduling/coverage");
}

export async function generatePayroll(
  period_start: string,
  period_end: string,
): Promise<PayrollRun> {
  return api<PayrollRun>("/api/v1/payroll/runs/generate", {
    method: "POST",
    body: JSON.stringify({ period_start, period_end }),
  });
}

export async function listPayrollRuns(): Promise<PayrollRun[]> {
  return api<PayrollRun[]>("/api/v1/payroll/runs");
}

export async function finalizePayroll(runId: number): Promise<PayrollRun> {
  return api<PayrollRun>(`/api/v1/payroll/runs/${runId}/finalize`, {
    method: "POST",
  });
}

export async function generateInvoices(
  period_start: string,
  period_end: string,
): Promise<Invoice[]> {
  return api<Invoice[]>("/api/v1/billing/invoices/generate", {
    method: "POST",
    body: JSON.stringify({ period_start, period_end }),
  });
}

export async function listInvoices(): Promise<Invoice[]> {
  return api<Invoice[]>("/api/v1/billing/invoices");
}

export async function issueInvoice(invoiceId: number): Promise<Invoice> {
  return api<Invoice>(`/api/v1/billing/invoices/${invoiceId}/issue`, {
    method: "POST",
  });
}

export async function recordInvoicePayment(
  invoiceId: number,
  amount: number,
): Promise<Invoice> {
  return api<Invoice>(`/api/v1/billing/invoices/${invoiceId}/payments`, {
    method: "POST",
    body: JSON.stringify({ amount }),
  });
}

export async function fetchCollections(): Promise<CollectionsSummary> {
  return api<CollectionsSummary>("/api/v1/billing/collections");
}

export async function downloadPayrollPayslipsPdf(runId: number): Promise<void> {
  const blob = await downloadFileBlob(`/api/v1/payroll/runs/${runId}/payslips.pdf`);
  triggerBlobDownload(blob, `payroll-${runId}-payslips.pdf`);
}

export async function downloadCaregiverPayslipPdf(
  runId: number,
  caregiverId: number,
): Promise<void> {
  const blob = await downloadFileBlob(
    `/api/v1/payroll/runs/${runId}/payslips/${caregiverId}.pdf`,
  );
  triggerBlobDownload(blob, `payslip-${runId}-cg${caregiverId}.pdf`);
}

export async function downloadStatutoryRegisterCsv(runId: number): Promise<void> {
  const blob = await downloadFileBlob(
    `/api/v1/payroll/runs/${runId}/statutory-register.csv`,
  );
  triggerBlobDownload(blob, `payroll-${runId}-statutory-register.csv`);
}

export async function downloadBankTransferCsv(runId: number): Promise<void> {
  const blob = await downloadFileBlob(
    `/api/v1/payroll/runs/${runId}/bank-transfer.csv`,
  );
  triggerBlobDownload(blob, `payroll-${runId}-bank-transfer.csv`);
}

export async function downloadInvoicePdf(invoiceId: number): Promise<void> {
  const blob = await downloadFileBlob(
    `/api/v1/billing/invoices/${invoiceId}/pdf`,
  );
  triggerBlobDownload(blob, `invoice-${invoiceId}.pdf`);
}

export async function runDocumentOcr(documentId: number): Promise<unknown> {
  return api(`/api/v1/documents/${documentId}/ocr`, { method: "POST" });
}
