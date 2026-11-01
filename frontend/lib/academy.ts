import { api } from "./api";

export type Readiness = {
  caregiver_id: number;
  readiness_score: number;
  readiness_band: string;
  breakdown: {
    verification: number;
    training: number;
    assessment: number;
    practical: number;
    conduct: number;
  };
  recommendations: string[];
};

export type Certification = {
  id: number;
  caregiver_id: number;
  certification_name: string;
  qualification_pack_code: string | null;
  issuing_body: string;
  issue_date: string | null;
  expiry_date: string | null;
  certificate_number: string | null;
  verification_status: string;
  is_expired: boolean;
};

export type MarketplaceRow = {
  id: number;
  first_name: string;
  last_name: string;
  years_experience: number | null;
  readiness_score: number;
  readiness_band: string;
  employability_score: number;
  verification_status_summary: string;
  languages: string[];
};

export function bandLabel(band: string) {
  if (band === "GOLD") return "Gold — Deployable";
  if (band === "SILVER") return "Silver — Minor training";
  if (band === "BRONZE") return "Bronze — Training needed";
  return "Not ready";
}

export function bandClass(band: string) {
  const b = band.toLowerCase();
  if (b === "gold") return "badge badge-low";
  if (b === "silver") return "badge badge-medium";
  if (b === "bronze") return "badge badge-high";
  return "badge";
}

export async function fetchReadiness(caregiverId: number): Promise<Readiness> {
  return api<Readiness>(`/api/v1/academy/caregivers/${caregiverId}/readiness`);
}

export async function fetchCertifications(caregiverId: number): Promise<Certification[]> {
  return api<Certification[]>(`/api/v1/academy/caregivers/${caregiverId}/certifications`);
}

export type TrainingProgram = {
  id: number;
  code: string;
  name: string;
};

export type ProgramEnrollment = {
  id: number;
  program_id: number;
  program_code: string;
  program_name: string;
  status: string;
  assessment_score: number | null;
};

export function normalizeEnrollment(row: ProgramEnrollment): ProgramEnrollment {
  return {
    ...row,
    program_code: (row.program_code || "").toUpperCase(),
    status: (row.status || "").toUpperCase(),
  };
}

export async function fetchTrainingPrograms(): Promise<TrainingProgram[]> {
  return api<TrainingProgram[]>("/api/v1/academy/training-programs");
}

export async function fetchEnrollments(
  caregiverId: number,
): Promise<ProgramEnrollment[]> {
  const rows = await api<ProgramEnrollment[]>(
    `/api/v1/academy/caregivers/${caregiverId}/enrollments`,
  );
  return rows.map(normalizeEnrollment);
}

export async function fetchMarketplace(params?: {
  readiness_min?: number;
  band?: string;
  qp_code?: string;
}): Promise<MarketplaceRow[]> {
  const q = new URLSearchParams();
  if (params?.readiness_min != null) q.set("readiness_min", String(params.readiness_min));
  if (params?.band) q.set("band", params.band);
  if (params?.qp_code) q.set("qp_code", params.qp_code);
  const suffix = q.toString() ? `?${q}` : "";
  return api<MarketplaceRow[]>(`/api/v1/academy/marketplace${suffix}`);
}
