/** Phase 4B: client sheet, care plan, risk register, handovers (backend app/livewell/client_care.py). */

export type Medicine = { name: string; dose: string; times: string };

export type ClientSheet = {
  elder_id: number;
  elder_name: string;
  date_of_birth?: string | null;
  address: string;
  phone: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  conditions: string;
  allergies: string;
  mobility: string;
  medicines: Medicine[];
  risks: string;
  language: string;
  doctor_name: string;
  doctor_phone: string;
  hospital_name: string;
  hospital_phone: string;
  family_preferences: string;
  updated_at: string | null;
  /** Staff and caregiver (visit day) only — never sent to the family. */
  keys_access?: string;
  open_risks?: { risk: string; level: RiskLevel; mitigation: string }[];
  updated_by?: string;
};

export type GoalStatus = "active" | "achieved" | "paused" | "stopped";
export type CareGoal = {
  id: number;
  goal: string;
  target_date: string | null;
  status: GoalStatus;
  status_label: string;
  interventions: string[];
  progress: string;
  updated_at: string | null;
};

export type CarePlanReview = {
  review_date: string | null;
  source: "set" | "reassessment" | null;
  reviewed_at: string | null;
  due: boolean;
  overdue: boolean;
};
export type CarePlan = { goals: CareGoal[]; review: CarePlanReview };

export type RiskLevel = "low" | "medium" | "high";
export type ClientRisk = {
  id: number;
  risk: string;
  level: RiskLevel;
  mitigation: string;
  owner_user_id: number | null;
  owner_name: string;
  review_date: string | null;
  review_overdue: boolean;
  status: "open" | "closed";
};

export type Handover = {
  id: number;
  kind: "shift" | "client_move";
  kind_label: string;
  elder_id: number | null;
  elder_name: string;
  from_name: string;
  to_user_id: number;
  to_name: string;
  note: string;
  created_at: string | null;
  acknowledged_at: string | null;
};

export type FamilyCareView = {
  sheet: ClientSheet;
  goals: CareGoal[];
  next_review: string | null;
};

export const GOAL_STATUS_LABEL: Record<GoalStatus, string> = {
  active: "Working on it",
  achieved: "Achieved",
  paused: "On hold",
  stopped: "Stopped",
};
export const RISK_LEVEL_LABEL: Record<RiskLevel, string> = { low: "Low", medium: "Medium", high: "High" };

/** "12 Mar 2027" from an ISO date (date-only strings are not shifted by time zone). */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" });
}
