import { api } from "@/lib/api";
import type { CareBaseline, SafeHomeVisit, VisitCheckin } from "./visit-types";

export async function fetchStaffVisits(elderId: number, days = 90): Promise<SafeHomeVisit[]> {
  return api<SafeHomeVisit[]>(`/api/v1/home-safety/visits?elder_id=${elderId}&days=${days}`);
}

export async function createStaffVisit(
  payload: {
    elder_id: number;
    visit_type: string;
    visited_at?: string;
    staff_name?: string;
    partner_id?: string;
    summary?: string;
    wellness_notes?: string;
    concerns?: string[];
    recommendations?: string;
    duration_minutes?: number | null;
    status?: string;
    checkin?: VisitCheckin | null;
    baseline?: Omit<CareBaseline, "updated_at"> | null;
    family_message?: string;
    photo_ids?: number[];
    location?: { lat: number; lng: number; accuracy_m?: number; captured_at?: string } | null;
  },
): Promise<SafeHomeVisit> {
  return api<SafeHomeVisit>("/api/v1/home-safety/visits", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchCareBaseline(elderId: number): Promise<CareBaseline> {
  return api<CareBaseline>(`/api/v1/home-safety/visits/baseline/${elderId}`);
}

export async function saveCareBaseline(
  elderId: number,
  payload: Omit<CareBaseline, "updated_at">,
): Promise<CareBaseline> {
  return api<CareBaseline>(`/api/v1/home-safety/visits/baseline/${elderId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export const SAFE_HOME_VISIT_TYPES = [
  "Baseline profile",
  "Home safety assessment",
  "Wellness visit",
  "Wellness check-in",
  "Modification follow-up",
  "Product installation",
  "Other",
] as const;
