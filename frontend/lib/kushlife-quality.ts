/** KushLife K3 + Phase 5 (#100 #106): monthly letter, vitals trend, voice notes, ratings, NPS, quality. */
import { getApiUrl, getStoredAuth } from "./api";

export type VitalKey = "bp_sys" | "bp_dia" | "spo2" | "pulse";
export type VitalsPoint = { date: string } & Partial<Record<VitalKey, number>>;
export type VitalsSeries = {
  days: number;
  points: VitalsPoint[];
  baseline: Partial<Record<VitalKey, number | null>>;
  label: string;
};

export type MonthlyLetter = {
  id: number;
  elder_id: number;
  month_start: string;
  month_label: string;
  status: "draft" | "approved";
  text: string;
  manager_note: string;
  next_plan: string;
  stats: Record<string, unknown>;
  approved_at: string | null;
  overdue?: boolean;
  elder_name?: string;
};

export type MonthlyPending = {
  items: { id: number; elder_id: number; elder_name: string; month_label: string; overdue: boolean }[];
  overdue: number;
};

export type VoiceNote = {
  id: number;
  job_id: number;
  duration_s: number | null;
  created_at: string | null;
  url: string;
  recorded_by_name?: string;
  share_with_family?: boolean;
};

export type QualityNumbers = {
  visits_done: number;
  on_time_pct: number | null;
  on_time_measured: number;
  kushlife_pct: number | null;
  avg_rating: number | null;
  ratings: number;
  incidents: number;
};

export type NpsSummary = { responses: number; promoters: number; passives: number; detractors: number; nps: number | null };

export type AgencyQuality = {
  days: number;
  agency: QualityNumbers;
  nps: NpsSummary;
  clients: (QualityNumbers & { elder_id: number; elder_name: string })[];
};

export type FeedbackRow = {
  kind: "rating" | "nps";
  id: number;
  elder_id: number;
  elder_name: string;
  score: number;
  comment: string;
  job_id: number | null;
  by_name: string;
  created_at: string | null;
};

/** Fetch an authenticated file (audio, PDF) and hand back an object URL for <audio> / a new tab. */
export async function authedObjectUrl(path: string): Promise<string> {
  const auth = getStoredAuth();
  const res = await fetch(`${getApiUrl()}${path}`, {
    headers: auth?.access_token ? { Authorization: `Bearer ${auth.access_token}` } : {},
  });
  if (!res.ok) throw new Error(res.status === 404 ? "Not found" : "Could not open the file");
  return URL.createObjectURL(await res.blob());
}

/** Open a PDF the API serves (staff or family) in a new tab. */
export async function openPdf(path: string): Promise<void> {
  const tab = window.open("", "_blank");
  try {
    const url = await authedObjectUrl(path);
    if (tab) tab.location.href = url;
    else window.location.href = url;
  } catch (e) {
    tab?.close();
    throw e;
  }
}

export function fmtPct(v: number | null | undefined): string {
  return v == null ? "—" : `${v}%`;
}
