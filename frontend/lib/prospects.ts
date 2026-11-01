import { api } from "./api";

export type PipelineStages = {
  elder_stages: string[];
  caregiver_stages: string[];
};

export type AssignableOwner = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
};

export type ElderProspect = {
  id: number;
  tenant_id: number;
  first_name: string;
  last_name: string;
  phone: string | null;
  email: string | null;
  address: string | null;
  source: string | null;
  stage: string;
  status: string;
  owner_user_id: number | null;
  owner_name: string | null;
  next_follow_up_at: string | null;
  lost_reason: string | null;
  notes: string | null;
  care_level: string | null;
  converted_elder_id: number | null;
  created_at: string;
  updated_at: string;
  // Website lead tracking (FIX 107/108)
  lead_source?: string | null;
  utm_source?: string | null;
  utm_medium?: string | null;
  utm_campaign?: string | null;
  referrer_url?: string | null;
  landing_page?: string | null;
  referral_code?: string | null;
  referred_by?: string | null;
  pincode?: string | null;
  area_served?: boolean | null;
  assessment_slot?: string | null;
  assessment_fee_paise?: number | null;
  assessment_paid?: boolean;
};

export type CaregiverProspect = {
  id: number;
  tenant_id: number;
  first_name: string;
  last_name: string;
  phone: string | null;
  email: string | null;
  address: string | null;
  source: string | null;
  stage: string;
  status: string;
  owner_user_id: number | null;
  owner_name: string | null;
  next_follow_up_at: string | null;
  lost_reason: string | null;
  notes: string | null;
  years_experience: number | null;
  converted_caregiver_id: number | null;
  resume_score: number | null;
  resume_document_id: number | null;
  has_resume: boolean;
  created_at: string;
  updated_at: string;
};

export type PipelineActivity = {
  id: number;
  activity_type: string;
  body: string;
  metadata: Record<string, unknown> | null;
  created_by_user_id: number | null;
  created_by_name: string | null;
  created_at: string;
};

export type ProspectFilters = {
  status?: string;
  stage?: string;
  owner_user_id?: number;
  overdue_only?: boolean;
};

function queryString(filters: ProspectFilters) {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.stage) params.set("stage", filters.stage);
  if (filters.owner_user_id != null) {
    params.set("owner_user_id", String(filters.owner_user_id));
  }
  if (filters.overdue_only) params.set("overdue_only", "true");
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export async function fetchPipelineStages() {
  return api<PipelineStages>("/api/v1/prospects/stages");
}

export async function fetchAssignableOwners() {
  return api<AssignableOwner[]>("/api/v1/prospects/owners");
}

export async function listElderProspects(filters: ProspectFilters = {}) {
  return api<ElderProspect[]>(`/api/v1/prospects/elders${queryString(filters)}`);
}

export async function getElderProspect(id: number) {
  return api<ElderProspect>(`/api/v1/prospects/elders/${id}`);
}

export async function createElderProspect(
  payload: Partial<ElderProspect> & { first_name: string; last_name: string },
) {
  return api<ElderProspect>("/api/v1/prospects/elders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateElderProspect(
  id: number,
  payload: Record<string, unknown>,
) {
  return api<ElderProspect>(`/api/v1/prospects/elders/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function convertElderProspect(
  id: number,
  opts?: { elder_id?: number | null },
) {
  const body =
    opts?.elder_id != null ? JSON.stringify({ elder_id: opts.elder_id }) : undefined;
  return api<{
    prospect: ElderProspect | null;
    elder_id: number;
    absorbed_prospect_id?: number | null;
    prospect_absorbed?: boolean;
  }>(
    `/api/v1/prospects/elders/${id}/convert`,
    {
      method: "POST",
      ...(body ? { body } : {}),
    },
  );
}

export async function unlinkElderProspect(id: number) {
  return api<ElderProspect>(`/api/v1/prospects/elders/${id}/unlink`, {
    method: "POST",
  });
}

export async function permanentlyDeleteElderProspect(id: number) {
  return api<{ deleted: string; id: number; name: string }>(
    `/api/v1/prospects/elders/${id}/permanent`,
    { method: "DELETE" },
  );
}

export async function permanentlyDeleteElder(id: number) {
  return api<{ deleted: string; id: number; name: string }>(
    `/api/v1/elders/${id}/permanent`,
    { method: "DELETE" },
  );
}

export async function listElderActivities(id: number) {
  return api<PipelineActivity[]>(
    `/api/v1/prospects/elders/${id}/activities`,
  );
}

export async function addElderActivity(
  id: number,
  payload: { activity_type: string; body: string },
) {
  return api<PipelineActivity>(`/api/v1/prospects/elders/${id}/activities`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listCaregiverProspects(filters: ProspectFilters = {}) {
  return api<CaregiverProspect[]>(
    `/api/v1/prospects/caregivers${queryString(filters)}`,
  );
}

export async function getCaregiverProspect(id: number) {
  return api<CaregiverProspect>(`/api/v1/prospects/caregivers/${id}`);
}

export async function createCaregiverProspect(
  payload: Partial<CaregiverProspect> & { first_name: string; last_name: string },
) {
  return api<CaregiverProspect>("/api/v1/prospects/caregivers", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateCaregiverProspect(
  id: number,
  payload: Record<string, unknown>,
) {
  return api<CaregiverProspect>(`/api/v1/prospects/caregivers/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function convertCaregiverProspect(id: number) {
  return api<{ prospect: CaregiverProspect; caregiver_id: number }>(
    `/api/v1/prospects/caregivers/${id}/convert`,
    { method: "POST" },
  );
}

export async function listCaregiverActivities(id: number) {
  return api<PipelineActivity[]>(
    `/api/v1/prospects/caregivers/${id}/activities`,
  );
}

export async function addCaregiverActivity(
  id: number,
  payload: { activity_type: string; body: string },
) {
  return api<PipelineActivity>(
    `/api/v1/prospects/caregivers/${id}/activities`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function stageLabel(stage: string) {
  return stage.replace(/_/g, " ");
}

export function formatFollowUp(iso: string | null) {
  if (!iso) return "—";
  const d = new Date(iso);
  const overdue = d.getTime() < Date.now();
  return `${d.toLocaleString()}${overdue ? " (overdue)" : ""}`;
}
