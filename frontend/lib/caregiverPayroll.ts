import { api, downloadFileBlob, triggerBlobDownload } from "./api";

export type CaregiverEarningsSummary = {
  caregiver_id: number;
  ytd_year: number;
  ytd_gross: number;
  ytd_net: number;
  ytd_hours: number;
  finalized_runs_count: number;
  last_period: {
    run_id: number;
    period_start: string;
    period_end: string;
    gross: number;
    deductions: number;
    net: number;
    hours: number;
  } | null;
};

export type CaregiverPayslipSummary = {
  run_id: number;
  period_start: string;
  period_end: string;
  gross: number;
  deductions: number;
  net: number;
  hours: number;
  finalized_at: string | null;
};

export async function fetchCaregiverEarnings(): Promise<CaregiverEarningsSummary> {
  return api<CaregiverEarningsSummary>("/api/v1/caregiver-portal/earnings");
}

export async function fetchCaregiverPayslips(): Promise<CaregiverPayslipSummary[]> {
  return api<CaregiverPayslipSummary[]>("/api/v1/caregiver-portal/payslips");
}

export async function downloadCaregiverPayslip(runId: number): Promise<void> {
  const blob = await downloadFileBlob(
    `/api/v1/caregiver-portal/payslips/${runId}.pdf`,
  );
  triggerBlobDownload(blob, `payslip-${runId}.pdf`);
}
