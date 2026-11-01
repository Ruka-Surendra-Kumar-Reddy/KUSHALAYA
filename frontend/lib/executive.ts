import { api } from "./api";

export type ExecutiveCriticalAlert = {
  code: string;
  level: string;
  title: string;
  message: string;
  metric_label?: string | null;
  metric_value?: number | null;
  metric_value_display?: string | null;
  change_percent?: number | null;
  recommended_action: string;
};

export type ExecutiveDashboard = {
  tenant_id: number;
  as_of_utc: string;
  critical_alerts: ExecutiveCriticalAlert[];
  executive_kpis: {
    total_workforce: number;
    active_workforce: number;
    bench_workforce: number;
    ready_for_deployment: number;
    placement_ready: number;
    in_training: number;
  };
  utilization: {
    utilization_percent: number | null;
    billable_percent: number | null;
    idle_percent: number | null;
    bench_percent: number | null;
    target_percent: number;
  };
  bench_intelligence: {
    bench_count: number;
    average_bench_days: number | null;
    bench_cost_inr: number;
    bench_cost_lakhs: number;
    bench_cost_change_percent: number;
    by_city: { city: string; count: number }[];
    by_category: Record<string, number>;
    recommendation: { summary: string; expected_savings_lakhs: number } | null;
    bench_cost_per_caregiver_month_inr?: number;
  };
  tenant_settings?: {
    bench_cost_per_caregiver_month_inr: number;
  };
  placement_intelligence: {
    placements_this_month: number;
    placement_velocity_change: number;
    placement_success_rate_percent: number | null;
    average_time_to_placement_days: number | null;
    average_time_is_proxy: boolean;
    pipeline_open_caregivers: number;
  };
  recruitment_funnel: { stage: string; count: number }[];
  demand_forecast: {
    period_days: number;
    categories: Record<string, number>;
    method: string;
  };
  readiness_tiers: Record<string, number>;
  attrition: {
    high_risk: number;
    medium_risk: number;
    low_risk: number;
    expected_attrition_next_month: number;
    recommendation: string | null;
  };
  financial: {
    monthly_revenue_inr: number;
    monthly_revenue_crores: number;
    payroll_expense_inr: number;
    bench_cost_inr: number;
    bench_cost_lakhs: number;
    profit_margin_percent: number | null;
    currency: string;
  };
  city_operations: {
    city: string;
    workforce: number;
    bench: number;
    assigned: number;
    utilization_percent: number | null;
  }[];
  marketplace: {
    available_workers: number;
    open_requests: number;
    potential_placements: number;
    note: string;
  };
  ai_insights: {
    id: string;
    title: string;
    body: string;
    recommendation: string;
  }[];
  scorecard: {
    overall_score: number;
    max_score: number;
    categories: Record<string, number>;
  };
  executive_copilot_questions: string[];
};

export async function fetchExecutiveDashboard(): Promise<ExecutiveDashboard> {
  return api<ExecutiveDashboard>("/api/v1/executive/dashboard");
}

export function formatInrLakhs(lakhs: number): string {
  return `₹${lakhs.toLocaleString("en-IN", { maximumFractionDigits: 2 })} Lakhs`;
}
