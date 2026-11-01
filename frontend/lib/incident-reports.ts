import { api } from "@/lib/api";

/** Incident reports (#97) — after-the-fact reports, not live SOS alerts. */
export const INCIDENT_KINDS: { value: string; label: string }[] = [
  { value: "fall", label: "Fall" },
  { value: "near_miss", label: "Near-miss" },
  { value: "medication_error", label: "Medication error" },
  { value: "injury", label: "Injury" },
  { value: "complaint", label: "Complaint" },
  { value: "other", label: "Other" },
];

export type FollowUp = { id?: string; action: string; owner: string; due_date: string | null; done: boolean };

export type IncidentReport = {
  id: number;
  elder_id: number;
  elder_name: string;
  care_job_id: number | null;
  kind: string;
  kind_label: string;
  serious: boolean;
  occurred_at: string | null;
  location: string;
  what_happened: string;
  injury: string;
  action_taken: string;
  witnesses: string;
  family_informed: boolean;
  family_informed_at: string | null;
  reported_by_name: string;
  reporter_role: string;
  status: "open" | "reviewed" | "closed";
  status_label: string;
  follow_ups: FollowUp[];
  staff_notes: string;
  family_summary: string;
  outcome: string;
  reviewed_at: string | null;
  closed_at: string | null;
  created_at: string | null;
};

export type IncidentCounts = { total: number; falls: number; falls_90d: number; open: number };

export type IncidentInput = {
  kind: string;
  what_happened: string;
  occurred_at?: string | null;
  location?: string;
  injury?: string;
  action_taken?: string;
  witnesses?: string;
  family_informed?: boolean;
  family_informed_at?: string | null;
  serious?: boolean;
};

const BASE = "/api/v1/home-safety/incident-reports";

export function listIncidents(elderId?: number) {
  return api<{ reports: IncidentReport[]; counts?: IncidentCounts }>(elderId ? `${BASE}?elder_id=${elderId}` : BASE);
}

export function createIncident(body: IncidentInput & { elder_id: number; follow_ups?: FollowUp[] }) {
  return api<IncidentReport>(BASE, { method: "POST", body: JSON.stringify(body) });
}

export function updateIncident(id: number, body: Partial<IncidentReport>) {
  return api<IncidentReport>(`${BASE}/${id}`, { method: "PUT", body: JSON.stringify(body) });
}

export function reviewIncident(id: number, body: { staff_notes?: string; family_summary?: string; follow_ups?: FollowUp[] }) {
  return api<IncidentReport>(`${BASE}/${id}/review`, { method: "POST", body: JSON.stringify(body) });
}

export function closeIncident(id: number, body: { outcome: string; family_summary?: string }) {
  return api<IncidentReport>(`${BASE}/${id}/close`, { method: "POST", body: JSON.stringify(body) });
}

export function fileCaregiverIncident(jobId: number, body: IncidentInput) {
  return api<IncidentReport>(`/api/v1/caregiver-portal/jobs/${jobId}/incident`, { method: "POST", body: JSON.stringify(body) });
}

/** A fall with an injury or any medication error tells the care manager at once. */
export function isSerious(kind: string, injury: string, flagged = false) {
  return flagged || kind === "medication_error" || (kind === "fall" && injury.trim() !== "");
}

/** `datetime-local` value → ISO with the India offset (all clients are in IST). */
export function localToIso(value: string): string | null {
  return value ? `${value}:00+05:30` : null;
}

// --- Per-client visit checklist (#99) ------------------------------------------------

export type ChecklistItem = { id: string; label: string; source?: string };
export type ChecklistResult = { id: string; label: string; done: boolean | null; reason: string };
export type ChecklistSuggestion = ChecklistItem & { already_added: boolean };

export function getVisitChecklist(elderId: number) {
  return api<{ items: ChecklistItem[]; updated_at: string | null; suggestions: ChecklistSuggestion[] }>(
    `/api/v1/home-safety/clients/${elderId}/visit-checklist`,
  );
}

export function saveVisitChecklist(elderId: number, items: ChecklistItem[]) {
  return api<{ items: ChecklistItem[]; updated_at: string | null }>(`/api/v1/home-safety/clients/${elderId}/visit-checklist`, {
    method: "PUT",
    body: JSON.stringify({ items }),
  });
}

/** One line for a visit report: "Checklist 2/3 — not done: Check feet (asleep); not ticked: Walk". */
export function checklistLine(results?: ChecklistResult[] | null): string {
  if (!results?.length) return "";
  const done = results.filter((r) => r.done === true).length;
  const no = results.filter((r) => r.done === false).map((r) => r.label + (r.reason ? ` (${r.reason})` : ""));
  const skipped = results.filter((r) => r.done == null).map((r) => r.label);
  return [
    `Checklist ${done}/${results.length}`,
    no.length ? `not done: ${no.join(", ")}` : "",
    skipped.length ? `not ticked: ${skipped.join(", ")}` : "",
  ]
    .filter(Boolean)
    .join(" — ");
}
