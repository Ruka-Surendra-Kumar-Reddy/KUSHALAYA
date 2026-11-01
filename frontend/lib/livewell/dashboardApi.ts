import { api } from "@/lib/api";

export type OpsDashboardSummary = {
  clients: number;
  assessments_open: number;
  assessments_total: number;
  visits_today: number;
  visits_total: number;
  catalog_items: number;
};

export async function fetchOpsDashboardSummary(): Promise<OpsDashboardSummary> {
  return api<OpsDashboardSummary>("/api/v1/home-safety/dashboard");
}
