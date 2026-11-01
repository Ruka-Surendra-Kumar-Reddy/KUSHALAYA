import { api, getStoredAuth } from "./api";
import { dayMonth } from "./ist";
import { optionalLocation } from "./visit-location";

/**
 * Field actions (assessment, photos, report) for one job. Caregivers use their
 * own routes; a care manager running the visit from the ops portal uses /jobs.
 */
export function isFieldStaff(): boolean {
  const role = getStoredAuth()?.role ?? "";
  return role === "CARE_MANAGER" || role === "TENANT_ADMIN" || role === "SYSTEM_ADMIN";
}

export function fieldJobBase(jobId: number): string {
  return isFieldStaff() ? `/api/v1/jobs/${jobId}` : `/api/v1/caregiver-portal/jobs/${jobId}`;
}

/** Scheduled work for a client — see backend app/livewell/care_jobs.py. */
export type JobKind = "visit" | "assessment" | "install";
export type JobStatus =
  | "requested"
  | "scheduled"
  | "on_the_way"
  | "checked_in"
  | "completed"
  | "cancelled"
  | "missed";

export type CareJob = {
  id: number;
  elder_id: number;
  elder_name: string;
  elder_address: string;
  /** Saved home pin (staff + own caregiver only), used for Directions. */
  elder_home?: { lat: number; lng: number } | null;
  /** Client's phone for tap-to-call (may be blank). */
  elder_phone?: string;
  kind: JobKind;
  kind_label: string;
  title: string;
  tasks: string;
  location: string;
  scheduled_at: string | null;
  duration_minutes: number | null;
  caregiver_id: number | null;
  caregiver_name: string;
  /** Assessments: the care manager doing it. */
  assignee_user_id?: number | null;
  assignee_name?: string;
  status: JobStatus;
  status_label: string;
  request_id: string | null;
  assessment_id: string | null;
  staff_note: string;
  caregiver_note: string;
  started_at: string | null;
  checked_in_at: string | null;
  completed_at: string | null;
  created_at: string | null;
  report?: {
    checks?: Record<string, string>;
    note?: string;
    photo_ids?: number[];
    hazard_ids?: string[];
    /** Per-client checklist results (#99); done null = not ticked. */
    checklist?: { id: string; label: string; done: boolean | null; reason: string }[];
  } | null;
  /** The client's visit checklist to tick on this visit (#99). */
  checklist?: { id: string; label: string; source?: string }[];
  photo_urls?: string[];
  know_them?: { approach: string; likes: string; avoid: string; routine: string; notes: string } | null;
  /** Staff list only: where check-in / check-out happened (lib/visit-location.ts). */
  visit_location?: import("./visit-location").VisitLocation | null;
  /** Staff list only, while on the way: caregiver position + rough ETA (lib/live-location.ts). */
  live?: import("./live-location").LiveOnTheWay | null;
  /** Set on create when the family request could not be linked (already cancelled or done). */
  note?: string;
};

export type JobInput = {
  elder_id: number;
  kind: JobKind;
  scheduled_at: string;
  caregiver_id?: number | null;
  /** Assessments: the care manager doing it (blank = the client's own care manager). */
  assignee_user_id?: number | null;
  title?: string;
  tasks?: string;
  location?: string;
  request_id?: string;
  product_ids?: string[];
  /** Book even when the caregiver or client is already booked then (after "Book anyway"). */
  force?: boolean;
};

/** The 409 double-booking message from the server ends with "Book anyway?". */
export function isClash(err: unknown): err is Error {
  return err instanceof Error && err.message.trim().endsWith("Book anyway?");
}

export const JOB_KIND_LABEL: Record<JobKind, string> = {
  visit: "Care visit",
  assessment: "Home safety assessment",
  install: "Product installation",
};

export function listJobs(params: { elder_id?: number; open_only?: boolean } = {}) {
  const q = new URLSearchParams();
  if (params.elder_id) q.set("elder_id", String(params.elder_id));
  if (params.open_only) q.set("open_only", "true");
  const qs = q.toString();
  return api<CareJob[]>(`/api/v1/jobs${qs ? `?${qs}` : ""}`);
}

export function createJob(input: JobInput) {
  return api<CareJob>("/api/v1/jobs", { method: "POST", body: JSON.stringify(input) });
}

/** An unfinished assessment: an open assessment job, or a draft record without one. */
export type AssessmentDraft = { job_id: number | null; assessment_id: string | null; answered: number; since: string | null };

/** "New assessment" choices: clients, then open leads (backend app/livewell/assessment_start.py). */
export type AssessmentTarget = {
  key: string;
  kind: "client" | "lead";
  elder_id: number | null;
  lead_id: number | null;
  name: string;
  phone?: string;
  /** Client / lead ID shown in "New assessment" (C12, L7). */
  ref?: string;
  draft: AssessmentDraft | null;
};

export type AssessmentFor = { elder_id: number } | { lead_id: number };

export function assessmentTargets() {
  return api<AssessmentTarget[]>("/api/v1/jobs/assessment-targets");
}

export function assessmentDraft(who: AssessmentFor) {
  const q = "elder_id" in who ? `elder_id=${who.elder_id}` : `lead_id=${who.lead_id}`;
  return api<{ draft: AssessmentDraft | null }>(`/api/v1/jobs/assessment-draft?${q}`);
}

/** Opens the checklist job: continues the open draft unless `fresh` (a new one). */
/** "Book assessment" on a new lead: an assessment job at that time; the lead moves to "Assessment booked". */
export function bookAssessment(body: { lead_id: number; scheduled_at: string; assignee_user_id?: number | null; force?: boolean }) {
  return api<{ job: CareJob; lead_id: number; stage: string }>("/api/v1/jobs/book-assessment", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function startAssessment(who: AssessmentFor, fresh = false) {
  return api<{ job_id: number; resumed: boolean; elder_id: number | null }>("/api/v1/jobs/start-assessment", {
    method: "POST",
    body: JSON.stringify({ ...who, new: fresh }),
  });
}

export function updateJob(id: number, patch: Partial<JobInput> & { status?: JobStatus }) {
  return api<CareJob>(`/api/v1/jobs/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
}

// Caregiver field app
export function myJobs() {
  return api<CareJob[]>("/api/v1/caregiver-portal/jobs");
}

export function setMyJobStatus(
  id: number,
  status: "on_the_way" | "checked_in" | "completed",
  extra: { latitude?: number; longitude?: number; accuracy?: number | null; note?: string } = {},
) {
  return api<CareJob>(`/api/v1/caregiver-portal/jobs/${id}/status`, {
    method: "POST",
    body: JSON.stringify({ status, ...extra }),
  });
}

export type FieldQuestion = {
  id: string;
  label: string;
  group: string;
  input_type: string;
  hint: string;
  /** Admin-set wording and answer options; empty = app defaults (question-options.ts). */
  ask?: string;
  options?: { label: string; rating: "excellent" | "acceptable" | "unsafe" | "na" }[];
};
export type FieldAssessment = {
  job: CareJob;
  categories: { id: string; title: string; items: FieldQuestion[] }[];
  /** Questions that didn't apply to this home last time — pre-marked "Not applicable". */
  skip_for_home?: string[];
  ratings: Record<string, string>;
  item_notes: Record<string, string>;
  /** The option tapped per question (report wording). */
  answer_labels?: Record<string, string>;
  resident_profile: Record<string, unknown>;
  notes: string;
  status: string;
  score: number | null;
  /** Step 1: the client's details and home location (backend field_assessment.client_info). */
  client?: AssessmentClient;
};

export type ClientDetails = {
  first_name: string;
  last_name: string;
  phone: string;
  gender: string;
  date_of_birth: string;
  address: string;
  area: string;
  city: string;
  pincode: string;
  email: string;
  emergency_contact_name: string;
  emergency_contact_phone: string;
  /** The contact person (usually the son / daughter who enquired). */
  contact_relation: string;
  contact_email: string;
};

export type HomeLocation = {
  mode: "auto" | "manual";
  latitude?: number;
  longitude?: number;
  accuracy?: number | null;
  label?: string;
  at?: string;
};

export type AssessmentClient = {
  details: ClientDetails;
  location: HomeLocation | null;
  /** More beneficiaries in the same home, besides the main one. */
  beneficiaries?: { name: string; gender: string; date_of_birth: string; relation: string; phone: string }[];
  missing: (keyof ClientDetails)[];
  is_lead: boolean;
  reassessment: boolean;
  confirmed: boolean;
};

/** One row on the Assessments page (backend assessment_start.board). */
export type AssessmentBoardRow = {
  key: string;
  job_id: number | null;
  assessment_id: string | null;
  status: "scheduled" | "in_progress" | "completed";
  job_status: JobStatus;
  client_name: string;
  client_phone: string;
  area: string;
  is_lead: boolean;
  elder_id: number | null;
  caregiver_id: number | null;
  caregiver_name: string;
  care_manager_id: number | null;
  care_manager_name: string;
  scheduled_at: string | null;
  updated_at: string | null;
  completed_at: string | null;
  answered: number;
  score: number | null;
  overdue_days: number;
  office: boolean;
};

export function assessmentBoard() {
  return api<AssessmentBoardRow[]>("/api/v1/jobs/assessment-board");
}

export function saveAssessmentClient(
  jobId: number,
  body: { details: ClientDetails; location: HomeLocation; beneficiaries?: AssessmentClient["beneficiaries"] },
) {
  return api<AssessmentClient>(`${fieldJobBase(jobId)}/assessment/client`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function loadFieldAssessment(jobId: number) {
  return api<FieldAssessment>(`${fieldJobBase(jobId)}/assessment`);
}

export function saveFieldAssessment(
  jobId: number,
  body: {
    ratings: Record<string, string>;
    item_notes: Record<string, string>;
    answer_labels?: Record<string, string>;
    resident_profile: Record<string, unknown>;
    notes?: string;
    complete?: boolean;
    latitude?: number;
    longitude?: number;
    accuracy?: number | null;
  },
  timeoutMs = 30_000,
) {
  // A hung request must not leave the checklist stuck on "Saving…" (iPad on weak Wi-Fi).
  const ctrl = typeof AbortController === "undefined" ? null : new AbortController();
  const timer = ctrl ? setTimeout(() => ctrl.abort(), timeoutMs) : null;
  return api<{ job: CareJob; status: string; score: number | null }>(`${fieldJobBase(jobId)}/assessment`, {
    method: "PUT",
    body: JSON.stringify(body),
    ...(ctrl ? { signal: ctrl.signal } : {}),
  })
    .catch((e: unknown) => {
      if (ctrl?.signal.aborted) throw new Error("No reply from the server. Check the internet connection and try again.");
      throw e;
    })
    .finally(() => {
      if (timer) clearTimeout(timer);
    });
}

/** "Thu 2 Oct, 10:30 am" in the viewer's locale. */
/** "Thu 8 Oct, 12:35 am" in India time (12-hour, like the rest of the ops app). */
export function jobWhen(iso: string | null): string {
  if (!iso) return "Time to be confirmed";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Time to be confirmed";
  const time = d
    .toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true, timeZone: "Asia/Kolkata" })
    .replace(/\s?(AM|PM)$/i, (_m, ap: string) => ` ${ap.toLowerCase()}`);
  return `${dayMonth(d, undefined, true)}, ${time}`;
}

export type FieldSuggestion = {
  product_id: number;
  name: string;
  category: string;
  price_with_gst_paise: number;
  priced: boolean;
  priority: "high" | "medium";
  reasons: { question_id: string; label: string; severity: "risk" | "attention" }[];
};

export function fieldSuggestions(jobId: number) {
  return api<FieldSuggestion[]>(`${fieldJobBase(jobId)}/suggestions`);
}

export async function uploadFieldPhoto(jobId: number, file: File, roomType: string) {
  const { postFormData } = await import("./api");
  const form = new FormData();
  form.append("file", file);
  form.append("room_type", roomType);
  return postFormData<{ document_id: number; count: number }>(`${fieldJobBase(jobId)}/photos`, form);
}


/**
 * Care manager moves a job along (On the way / Arrived) for the caregiver.
 * Arrived sends the browser's location when it gives one; office staff are not blocked.
 */
export async function staffProgress(id: number, status: "on_the_way" | "checked_in") {
  const where = status === "checked_in" ? await optionalLocation() : null;
  return api<CareJob>(`/api/v1/jobs/${id}/progress`, { method: "POST", body: JSON.stringify({ status, ...where }) });
}

/** A care manager on the way shares their browser position (only the newest is kept). */
export async function staffShareLocation(id: number, pos: { latitude: number; longitude: number; accuracy?: number | null }) {
  return api<{ tracking: boolean; track_path?: string | null }>(`/api/v1/jobs/${id}/location`, {
    method: "POST",
    body: JSON.stringify(pos),
  });
}

/** True when `iso` falls on today's date in India time. */
export function isTodayIST(iso: string | null | undefined): boolean {
  if (!iso) return false;
  const day = (d: Date) => d.toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
  return day(new Date(iso)) === day(new Date());
}

/**
 * Mark a booked field job (assessment) as arrived, then open it in the field app.
 * Only "already checked in" is ignored; any other error is thrown for the caller to show.
 * Callers confirm first when the job is not booked for today (see isTodayIST).
 */
export async function startFieldJob(job: { id: number; status?: string | null }) {
  if (job.status !== "checked_in") {
    try {
      await staffProgress(job.id, "checked_in");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (!/from checked in/i.test(msg)) throw e;
    }
  }
  window.location.href = `/caregiver/assess/${job.id}`;
}
