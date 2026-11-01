import { api } from "./api";
import type { CareJob } from "./jobs";

/** Repeating visits, weekly roster, leave and cover — backend app/api/v1/schedule.py. */

export const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

export type SeriesClash = { date: string; reason: string; job_id: number };

export type CareSeries = {
  id: number;
  elder_id: number;
  elder_name: string;
  caregiver_id: number | null;
  caregiver_name: string;
  title: string;
  tasks: string;
  weekdays: number[];
  days_label: string;
  time: string;
  duration_minutes: number;
  start_date: string;
  end_date: string | null;
  generated_until: string | null;
  status: "active" | "ended";
  previous_id: number | null;
  clashes: SeriesClash[];
  summary: string;
};

export type SeriesResult = {
  series: CareSeries;
  created: number;
  clashes: SeriesClash[];
  removed?: number;
  previous_id?: number;
  /** One-off changes kept when "this and following" rebuilt the repeating visits. */
  kept?: CareJob[];
};

export type SeriesInput = {
  elder_id: number;
  caregiver_id?: number | null;
  weekdays: number[];
  time: string;
  duration_minutes: number;
  start_date?: string;
  end_date?: string;
  weeks?: number;
  title?: string;
  tasks?: string;
};

export type SeriesChange = {
  job_id: number;
  scope: "one" | "following";
  time?: string;
  caregiver_id?: number | null;
  weekdays?: number[];
  duration_minutes?: number;
  force?: boolean;
};

export type RosterChip = {
  id: number;
  elder_id: number;
  elder_name: string;
  title: string;
  kind: string;
  status: string;
  start: string;
  end: string;
  scheduled_at: string;
  duration_minutes: number;
  caregiver_id: number | null;
  series_id: number | null;
  /** Booked while the caregiver is on approved leave: someone else must take it. */
  needs_cover?: boolean;
};

export type RosterCell = {
  date: string;
  visits: RosterChip[];
  leave: { id: number; status: string; type: string } | null;
};

export type RosterRow = {
  caregiver_id: number | null;
  name: string;
  active: boolean;
  /** Caregiver from another manager's team covering one of our visits ("Other team: <name>"). */
  other_team?: boolean;
  days: RosterCell[];
};

export type Roster = {
  week_start: string;
  days: { date: string; label: string }[];
  caregivers: RosterRow[];
  unassigned: RosterRow | null;
};

export type Leave = {
  id: number;
  caregiver_id: number;
  caregiver_name: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  reason: string | null;
  status: "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED";
  resolution_note: string | null;
  affected_count?: number;
};

export type CoverSuggestion = {
  caregiver_id: number;
  name: string;
  phone: string;
  same_team: boolean;
  knows_client: boolean;
  visits_that_day: number;
};

const S = "/api/v1/schedule";
const post = <T,>(path: string, body: unknown) => api<T>(path, { method: "POST", body: JSON.stringify(body) });

export const listSeries = (elderId?: number) => api<CareSeries[]>(`${S}/series${elderId ? `?elder_id=${elderId}` : ""}`);
export const createSeries = (input: SeriesInput) => post<SeriesResult>(`${S}/series`, input);
export const changeSeries = (id: number, change: SeriesChange) =>
  post<SeriesResult & { job?: CareJob }>(`${S}/series/${id}/change`, change);
export const endSeries = (id: number, endDate?: string) =>
  post<{ series: CareSeries; removed: number }>(`${S}/series/${id}/end`, endDate ? { end_date: endDate } : {});
export const getRoster = (week?: string) => api<Roster>(`${S}/roster${week ? `?week=${week}` : ""}`);

export const listLeave = (status?: string) => api<Leave[]>(`${S}/leave${status ? `?status=${status}` : ""}`);
export const addLeave = (input: {
  caregiver_id: number;
  leave_type: string;
  start_date: string;
  end_date: string;
  reason?: string;
  approve?: boolean;
}) => post<{ leave: Leave; affected: CareJob[] }>(`${S}/leave`, input);
export const approveLeave = (id: number) => post<{ leave: Leave; affected: CareJob[] }>(`${S}/leave/${id}/approve`, {});
export const rejectLeave = (id: number, reason?: string) => post<{ leave: Leave }>(`${S}/leave/${id}/reject`, { reason });
export const affectedVisits = (id: number) => api<CareJob[]>(`${S}/leave/${id}/affected`);
export const findCover = (jobId: number) =>
  api<{ job: CareJob; suggestions: CoverSuggestion[]; busy_count: number }>(`${S}/cover/${jobId}`);
export const reassign = (jobIds: number[], caregiverId: number | null, force = false) =>
  post<{ moved: CareJob[]; failed: { job_id: number; reason: string }[] }>(`${S}/reassign`, {
    job_ids: jobIds,
    caregiver_id: caregiverId,
    force,
  });

// Caregiver app
export const myLeave = () => api<Leave[]>("/api/v1/caregiver-portal/leave");
export const requestMyLeave = (input: { leave_type: string; start_date: string; end_date: string; reason?: string }) =>
  post<Leave>("/api/v1/caregiver-portal/leave", input);
export const cancelMyLeave = (id: number) => post<Leave>(`/api/v1/caregiver-portal/leave/${id}/cancel`, {});

export const LEAVE_TYPES: { id: string; label: string }[] = [
  { id: "ANNUAL", label: "Annual" },
  { id: "SICK", label: "Sick" },
  { id: "UNPAID", label: "Unpaid" },
  { id: "OTHER", label: "Other" },
];

export const LEAVE_STATUS_LABEL: Record<Leave["status"], string> = {
  PENDING: "Waiting for approval",
  APPROVED: "Approved",
  REJECTED: "Not approved",
  CANCELLED: "Cancelled",
};

/** Today's date in India as YYYY-MM-DD. */
export function istToday(): string {
  return new Date(Date.now() + 5.5 * 3600000).toISOString().slice(0, 10);
}

/** Add days to a YYYY-MM-DD date. */
export function addDays(ymd: string, days: number): string {
  const d = new Date(`${ymd}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

/** "14:30" → "2:30 pm" (the one ops time format, see lib/ist.ts timeIST). */
export function time12(hhmm: string): string {
  const m = /^(\d{1,2}):(\d{2})/.exec(hhmm || "");
  if (!m) return hhmm;
  const h = Number(m[1]);
  return `${h % 12 || 12}:${m[2]} ${h < 12 ? "am" : "pm"}`;
}

/** "10:00"–"11:00" → "10:00–11:00 am"; across noon → "11:30 am–12:30 pm". */
export function time12Range(start: string, end: string): string {
  const a = time12(start);
  const b = time12(end);
  return a.slice(-2) === b.slice(-2) ? `${a.slice(0, -3)}–${b}` : `${a}–${b}`;
}

export function shortDay(ymd: string): string {
  return new Date(`${ymd}T00:00:00Z`).toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}
