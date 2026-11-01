import { api } from "./api";

export type BenchMetrics = {
  total_bench: number;
  by_category: Record<string, number>;
  by_city: { city: string; count: number }[];
  by_language: { language: string; count: number }[];
  average_bench_days: number | null;
  deployment_ready_count: number;
};

export type BenchCaregiver = {
  caregiver_id: number;
  name: string;
  category: string;
  readiness_score: number;
  readiness_band: string;
  bench_days: number;
  city: string | null;
  languages: string[];
  skills: string[];
  top_gaps: string[];
};

export type BenchResponse = {
  tenant_id: number;
  as_of_utc: string;
  metrics: BenchMetrics;
  caregivers: BenchCaregiver[];
};

export type WorkforceAlert = {
  code: string;
  severity: string;
  title: string;
  message: string;
  metric_value?: number | null;
};

export type WorkforceDashboard = {
  tenant_id: number;
  as_of_utc: string;
  workforce: {
    caregivers_active: number;
    caregivers_on_bench: number;
    caregivers_assigned: number;
    utilization_percent: number | null;
    deployment_ready_on_bench: number;
  };
  elders: {
    active: number;
    without_active_assignment: number;
  };
  assignments: {
    active: number;
    started_this_month: number;
    started_last_month: number;
    placement_starts_this_month: number;
    placement_starts_last_month: number;
  };
  pipeline: {
    elder_prospects_open: number;
    caregiver_prospects_open: number;
    overdue_recruiter_follow_ups: number;
  };
  operations: {
    pending_document_reviews: number;
    open_incidents: number;
    attendance_check_ins_today: number;
    visits_scheduled_next_7_days: number;
    matching_runs_last_30_days: number;
  };
  placement_velocity: {
    assignments_started_this_month: number;
    assignments_started_last_month: number;
    placement_starts_this_month: number;
    placement_starts_last_month: number;
    month_over_month_placement_change: number;
  };
  recruitment_funnel: { stage: string; count: number }[];
  alerts: WorkforceAlert[];
  bench_summary: BenchMetrics;
};

export function benchCategoryLabel(
  code: string,
  t?: (key: string) => string,
): string {
  if (t) {
    const label = t(`workforce.categories.${code}`);
    if (label !== `workforce.categories.${code}`) return label;
  }
  return code;
}

export async function fetchWorkforceDashboard(): Promise<WorkforceDashboard> {
  return api<WorkforceDashboard>("/api/v1/workforce/dashboard");
}

export async function fetchWorkforceBench(
  category?: string,
): Promise<BenchResponse> {
  const q = category ? `?category=${encodeURIComponent(category)}` : "";
  return api<BenchResponse>(`/api/v1/workforce/bench${q}`);
}
