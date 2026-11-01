import { api } from "./api";

export type VisitChecklistItem = {
  code: string;
  title: string;
  required: boolean;
  completed: boolean;
  log_id: number | null;
};

export type VisitChecklist = {
  elder_id: number;
  log_date: string;
  vertical_label: string;
  items: VisitChecklistItem[];
  required_total: number;
  required_completed: number;
  incident_types: { value: string; label: string }[];
};

export type VisitCareNote = {
  id: number;
  elder_id: number;
  caregiver_id: number;
  caregiver_name?: string | null;
  note_type: string;
  body: string;
  note_date: string;
  created_at: string;
  vertical_label: string;
};

export const NOTE_TYPES = [
  { value: "GENERAL", label: "General update" },
  { value: "HANDOVER", label: "Handover to family" },
  { value: "CONCERN", label: "Concern / watch item" },
] as const;

export const INCIDENT_SEVERITIES = [
  { value: "LOW", label: "Low" },
  { value: "MEDIUM", label: "Medium" },
  { value: "HIGH", label: "High" },
  { value: "CRITICAL", label: "Critical" },
] as const;

export async function fetchVisitChecklist(elderId: number) {
  return api<VisitChecklist>(
    `/api/v1/visit-execution/checklist?elder_id=${elderId}`,
  );
}

export async function logChecklistItem(payload: {
  elder_id: number;
  item_code: string;
  completed: boolean;
  assignment_id?: number;
  attendance_id?: number | null;
}) {
  return api(`/api/v1/visit-execution/checklist`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchVisitNotesToday(elderId: number) {
  return api<VisitCareNote[]>(
    `/api/v1/visit-execution/notes?elder_id=${elderId}`,
  );
}

export async function fetchStaffVisitNotes(elderId: number, days = 30) {
  return api<VisitCareNote[]>(
    `/api/v1/visit-execution/notes/history?elder_id=${elderId}&days=${days}`,
  );
}

export async function fetchFamilyVisitNotes(days = 30) {
  return api<VisitCareNote[]>(
    `/api/v1/family-portal/visit-notes?days=${days}`,
  );
}

export function noteTypeLabel(value: string) {
  return (
    NOTE_TYPES.find((t) => t.value === value)?.label ??
    value.replace(/_/g, " ")
  );
}

export async function createVisitNote(payload: {
  elder_id: number;
  note_type: string;
  body: string;
  assignment_id?: number;
  attendance_id?: number | null;
}) {
  return api<VisitCareNote>("/api/v1/visit-execution/notes", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function reportFieldIncident(payload: {
  elder_id: number;
  incident_type: string;
  severity: string;
  description: string;
  assignment_id?: number;
}) {
  return api("/api/v1/visit-execution/incidents", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
