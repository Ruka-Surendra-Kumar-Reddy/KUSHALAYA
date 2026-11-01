import { api } from "./api";
import type { Visit } from "./tier1";

export type AutoScheduleProposal = {
  assignment_id: number;
  elder_id: number;
  caregiver_id: number;
  elder_name?: string | null;
  caregiver_name?: string | null;
  day: string;
  scheduled_start: string;
  scheduled_end: string;
  action: string;
  score: number | null;
  reasons: string[];
};

export type AutoScheduleResult = {
  mode: "preview" | "applied";
  created: number;
  proposed: number;
  skipped: number;
  conflicts: number;
  assignments: number;
  uncovered_clients: {
    elder_id: number;
    elder_name: string;
    schedule_days: string[];
  }[];
  proposals: AutoScheduleProposal[];
};

export async function autoGenerateSchedule(payload: {
  start_date: string;
  end_date: string;
  default_start_hour?: number;
  default_duration_hours?: number;
  max_hours_per_week?: number;
  dry_run: boolean;
}): Promise<AutoScheduleResult> {
  return api<AutoScheduleResult>("/api/v1/scheduling/auto-generate", {
    method: "POST",
    body: JSON.stringify({
      default_start_hour: 9,
      default_duration_hours: 4,
      max_hours_per_week: 48,
      ...payload,
    }),
  });
}

export type { Visit };
