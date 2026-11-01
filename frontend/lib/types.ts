export type User = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: string;
  tenant_id: number | null;
};

export type Elder = {
  id: number;
  tenant_id: number;
  first_name: string;
  last_name: string;
  date_of_birth?: string | null;
  gender?: string | null;
  care_level?: string | null;
  mobility_status?: string | null;
  phone?: string | null;
  address?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  medical_conditions?: string | null;
  allergies?: string | null;
  status: string;
  custom_attributes?: Record<string, unknown> | null;
};

export type Caregiver = {
  id: number;
  tenant_id: number;
  first_name: string;
  last_name: string;
  years_experience?: number | null;
  phone?: string | null;
  email?: string | null;
  aadhaar_number?: string | null;
  background_check_status?: string | null;
  police_verification_status?: string | null;
  status: string;
  custom_attributes?: Record<string, unknown> | null;
};

export type Assignment = {
  id: number;
  tenant_id: number;
  elder_id: number;
  caregiver_id: number;
  match_score?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  status: string;
};

export type DocumentRow = {
  id: number;
  entity_type: string;
  entity_id: number;
  document_type: string;
  file_name: string;
  verification_status: string;
  rejection_reason?: string | null;
};

export type VerticalInfo = {
  id: string;
  label: string;
  description: string;
};

export type Tenant = {
  id: number;
  name: string;
  email: string;
  phone: string;
  address: string;
  city: string;
  state: string;
  country: string;
  market?: string;
  status: string;
  vertical?: string;
  theme?: string;
  logo_url?: string | null;
  portal_title?: string | null;
};

export type Recommendation = {
  rank: number;
  match_result_id: number;
  caregiver_id: number;
  caregiver_name: string;
  match_score: number;
  confidence_score?: number;
  reasons: string[];
  component_scores?: Record<string, number>;
};

export type Skill = {
  id: number;
  code: string;
  name: string;
  category?: string | null;
};

export type CameraEvent = {
  id: number;
  tenant_id: number;
  elder_id: number;
  event_type: string;
  event_timestamp: string;
  severity: string | null;
  clip_url?: string | null;
  snapshot_url?: string | null;
  metadata?: Record<string, unknown> | null;
};

export type Incident = {
  id: number;
  tenant_id: number;
  elder_id: number;
  caregiver_id: number | null;
  source_event_id?: number | null;
  incident_type: string;
  severity: string;
  description: string | null;
  status: string;
  created_at: string;
  resolved_at: string | null;
};

export type MonitoringSummary = {
  total_events_24h: number;
  open_incidents: number;
  critical_alerts: number;
  events_by_type: Record<string, number>;
};
