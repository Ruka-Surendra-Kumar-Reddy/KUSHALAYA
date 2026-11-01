import { api } from "@/lib/api";
import { markPressedHere } from "@/lib/sos-siren";

/** Mirrors backend/app/api/v1/incidents.py. */

export type IncidentKind =
  | "sos_button"
  | "fall"
  | "immobility"
  | "device_offline"
  | "battery_low"
  | "family_sos"
  | "staff_emergency"
  | "other";

export type IncidentStatus = "open" | "acknowledged" | "escalated" | "resolved" | "closed";

export type IncidentOutcome =
  | "contacted_family"
  | "contacted_elder"
  | "dispatched"
  | "false_alarm"
  | "device_issue"
  | "resolved_home"
  | "hospital_admission"
  | "other";

export const INCIDENT_OUTCOMES: { value: IncidentOutcome; label: string }[] = [
  { value: "contacted_family", label: "Contacted family" },
  { value: "contacted_elder", label: "Contacted the client" },
  { value: "dispatched", label: "Dispatched someone" },
  { value: "false_alarm", label: "False alarm" },
  { value: "device_issue", label: "Device issue" },
  { value: "other", label: "Other (note required)" },
];

export type IncidentEvent = {
  id: number;
  at: string;
  event: string;
  channel: string | null;
  recipient: string | null;
  ok: boolean;
  detail: string | null;
  actor_user_id: number | null;
  actor_name: string | null;
};

export type Incident = {
  id: number;
  tenant_id: number;
  elder_id: number;
  elder_name: string | null;
  kind: IncidentKind;
  kind_label: string;
  severity: "critical" | "warning" | "info";
  status: IncidentStatus;
  source: "device" | "family" | "staff";
  device_mac: string | null;
  hub_key: string | null;
  dedupe_key: string | null;
  note: string | null;
  opened_at: string;
  minutes_open: number;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  escalated_at: string | null;
  escalation_level: number;
  resolved_at: string | null;
  resolved_by: string | null;
  outcome: string | null;
  resolution_note: string | null;
  legacy_id: string | null;
  owner_user_id?: number | null;
  owner_name?: string | null;
  details?: EmergencyDetails | null;
  elder_phone?: string | null;
  elder_address?: string | null;
  elder_home?: { lat: number; lng: number } | null;
  family_phone?: string | null;
  family_name?: string | null;
  partners?: PartnerLink[] | null;
  events?: IncidentEvent[];
  /** SOS steps: care team first, the family only after "Notify family" (29 Oct). */
  sos?: SosSteps | null;
};

export type SosSteps = {
  source: string;
  pressed_by: string;
  family_held: boolean;
  confirmed_at: string | null;
  confirmed_by: string | null;
  family_notified_at: string | null;
  family_notified_by: string | null;
  can_confirm: boolean;
  can_notify_family: boolean;
};

export type EmergencyStep = {
  at: string;
  by_user_id: number;
  by_name: string;
  hospital_name?: string;
  note?: string;
};

export type EmergencyDetails = {
  type?: string;
  type_label?: string;
  reported_by?: string;
  reported_by_label?: string;
  reporter_phone?: string | null;
  raised_by_name?: string;
  hospital_name?: string;
  steps?: Record<string, EmergencyStep>;
};

export type PartnerLink = {
  id: number;
  name: string;
  type: string;
  email: string | null;
  phone: string | null;
  sent_at: string;
  expires_at: string;
  last_status: string | null;
  last_status_label: string | null;
  last_response_at: string | null;
};

export type Option = { value: string; label: string };

export type EmergencyPartner = {
  id: string;
  name: string;
  phone: string;
  email: string;
  type: "ambulance" | "hospital" | "internal";
};

export type EmergencyOptions = {
  types: Option[];
  reporters: Option[];
  steps: Option[];
  outcomes: Option[];
  partner_statuses: Option[];
  partners: EmergencyPartner[];
  idle_minutes: number;
};

export type EmergencyRaise = {
  elder_id: number;
  type: string;
  reported_by: string;
  reporter_phone?: string | null;
  note?: string | null;
  job_id?: number | null;
};

export type IncidentSummary = {
  open: number;
  acknowledged: number;
  escalated: number;
  critical: number;
  total: number;
};

const BASE = "/api/v1/care/incidents";

export function fetchIncidentSummary(): Promise<IncidentSummary> {
  return api<IncidentSummary>(`${BASE}/summary`);
}

export function fetchIncidents(status?: string): Promise<Incident[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return api<Incident[]>(`${BASE}${qs}`);
}

export function fetchIncident(id: number): Promise<Incident> {
  return api<Incident>(`${BASE}/${id}`);
}

export function acknowledgeIncident(id: number): Promise<Incident> {
  return api<Incident>(`${BASE}/${id}/acknowledge`, { method: "POST" });
}

const SIREN = "/api/v1/sos-siren/incidents";

/** "It's real": the family is still not told (that is notifySosFamily). */
export async function confirmSos(id: number): Promise<Incident> {
  await api(`${SIREN}/${id}/confirm`, { method: "POST" });
  return api<Incident>(`${BASE}/${id}`);
}

/** After confirming: alert all the client's family logins, with an optional short message. */
export async function notifySosFamily(id: number, message?: string): Promise<Incident> {
  await api(`${SIREN}/${id}/notify-family`, { method: "POST", body: JSON.stringify({ message: message || null }) });
  return api<Incident>(`${BASE}/${id}`);
}

/** Close before the family is told; a family member who pressed it sees it was checked. */
export async function falseAlarmSos(id: number): Promise<Incident> {
  await api(`${SIREN}/${id}/false-alarm`, { method: "POST", body: JSON.stringify({}) });
  return api<Incident>(`${BASE}/${id}`);
}

export function escalateIncident(id: number, reason?: string): Promise<Incident> {
  return api<Incident>(`${BASE}/${id}/escalate`, {
    method: "POST",
    body: JSON.stringify({ reason: reason || null }),
  });
}

export function resolveIncident(
  id: number,
  outcome: IncidentOutcome,
  note?: string,
): Promise<Incident> {
  return api<Incident>(`${BASE}/${id}/resolve`, {
    method: "POST",
    body: JSON.stringify({ outcome, note: note || null }),
  });
}

export function noteIncident(id: number, note: string): Promise<Incident> {
  return api<Incident>(`${BASE}/${id}/note`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });
}

// --- Staff-raised emergency (Phase 3D) ---

export function fetchEmergencyOptions(): Promise<EmergencyOptions> {
  return api<EmergencyOptions>(`${BASE}/emergency/options`);
}

export function raiseEmergency(body: EmergencyRaise): Promise<Incident> {
  markPressedHere(); // this device stays quiet for its own SOS; the account's other devices ring
  return api<Incident>(`${BASE}/emergency`, { method: "POST", body: JSON.stringify(body) });
}

export function tickEmergencyStep(
  id: number,
  step: string,
  extra: { hospital_name?: string; note?: string } = {},
): Promise<Incident> {
  return api<Incident>(`${BASE}/${id}/emergency/step`, {
    method: "POST",
    body: JSON.stringify({ step, ...extra }),
  });
}

export function takeEmergencyOwnership(id: number, userId?: number): Promise<Incident> {
  return api<Incident>(`${BASE}/${id}/emergency/owner`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId ?? null }),
  });
}

export function closeEmergency(id: number, outcome: string, note: string): Promise<Incident> {
  return api<Incident>(`${BASE}/${id}/emergency/close`, {
    method: "POST",
    body: JSON.stringify({ outcome, note }),
  });
}

export function notifyEmergencyPartner(id: number, partnerId: string, message?: string): Promise<Incident> {
  return api<Incident>(`${BASE}/${id}/emergency/notify-partner`, {
    method: "POST",
    body: JSON.stringify({ partner_id: partnerId, message: message || null }),
  });
}

export function fetchEmergencyPartners(): Promise<{ partners: EmergencyPartner[]; idle_minutes: number }> {
  return api(`${BASE}/emergency/partners`);
}

export function saveEmergencyPartners(body: {
  partners?: Partial<EmergencyPartner>[];
  idle_minutes?: number;
}): Promise<{ partners: EmergencyPartner[]; idle_minutes: number }> {
  return api(`${BASE}/emergency/partners`, { method: "PUT", body: JSON.stringify(body) });
}
