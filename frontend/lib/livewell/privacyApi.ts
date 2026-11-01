import { api, downloadFileBlob } from "@/lib/api";

/** DPDP (#104): privacy notice, consent, data export and delete requests. */

export type PrivacyPurpose = {
  key: "care_delivery" | "health_data" | "location_sharing" | "marketing";
  label: string;
  text: string;
  required: boolean;
  default: boolean;
};

export type GrievanceOfficer = {
  name: string;
  role?: string;
  email: string;
  phone: string;
  response_days?: number;
};

export type PrivacyNotice = {
  version: string;
  sections: { heading: string; body: string }[];
  purposes: PrivacyPurpose[];
  grievance_officer: GrievanceOfficer;
};

export type ConsentRecord = {
  id: number;
  subject: "family" | "elder";
  elder_id: number | null;
  notice_version: string;
  purposes: Record<string, boolean>;
  consented_by_name: string;
  relationship: string | null;
  created_at: string | null;
  current: boolean;
};

export type DataRequest = {
  id: number;
  kind: string;
  scope: "account" | "household";
  status: "PENDING" | "REJECTED" | "COMPLETED";
  elder_id: number | null;
  /** Not sent by the API yet; the page falls back to "Client #id". */
  elder_name?: string | null;
  user_id: number | null;
  requester: string;
  reason: string | null;
  review_note: string | null;
  created_at: string | null;
  reviewed_at: string | null;
  completed_at: string | null;
  result: Record<string, unknown> | null;
};

export type ConsentStatus = {
  notice_version: string;
  needs_consent: boolean;
  consent: ConsentRecord | null;
  elders: { elder_id: number; name: string; consent: ConsentRecord | null; needs_consent: boolean }[];
  pending_delete_request: DataRequest | null;
};

export type ConsentPayload = {
  purposes: Record<string, boolean>;
  consented_by_name?: string;
  elders?: { elder_id: number; purposes: Record<string, boolean>; consented_by_name?: string; relationship?: string }[];
};

export type BackupStatus = {
  configured: boolean;
  ok: boolean;
  stale?: boolean;
  last_attempt_at?: string | null;
  last_success_at?: string | null;
  last_status?: string | null;
  remote?: string | null;
  db_bytes?: number | null;
  uploads_bytes?: number | null;
  restore_test_at?: string | null;
  restore_test_status?: string | null;
  restore_test_detail?: string | null;
  message?: string | null;
};

const FAMILY = "/api/v1/home-safety/family/privacy";
const ADMIN = "/api/v1/home-safety/privacy";

export const fetchPrivacyNotice = () => api<PrivacyNotice>(`${FAMILY}/notice`);
export const fetchConsentStatus = () => api<ConsentStatus>(`${FAMILY}/consent`);
export const saveConsent = (payload: ConsentPayload) =>
  api<ConsentStatus>(`${FAMILY}/consent`, { method: "POST", body: JSON.stringify(payload) });
export const requestAccountDelete = (scope: "account" | "household", reason: string) =>
  api<DataRequest>(`${FAMILY}/delete-request`, { method: "POST", body: JSON.stringify({ scope, reason }) });

export async function downloadMyData(): Promise<void> {
  const blob = await downloadFileBlob(`${FAMILY}/export`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `my-data-${new Date().toISOString().slice(0, 10)}.zip`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const fetchDataRequests = (status?: string) =>
  api<DataRequest[]>(`${ADMIN}/requests${status ? `?status=${encodeURIComponent(status)}` : ""}`);
export const reviewDataRequest = (id: number, action: "approve" | "reject", note: string) =>
  api<DataRequest>(`${ADMIN}/requests/${id}/${action}`, { method: "POST", body: JSON.stringify({ note }) });
export const fetchBackupStatus = () => api<BackupStatus>(`${ADMIN}/backup-status`);
