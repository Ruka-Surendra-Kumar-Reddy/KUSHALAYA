import { api } from "./api";

export type WorkflowDefinition = {
  id: string;
  name: string;
  description?: string;
  verticals: string[];
  enabled: boolean;
  trigger: { event?: string };
  conditions: Record<string, unknown>;
  actions: Record<string, unknown>[];
};

export type WorkflowConfig = {
  disabled_workflow_ids: string[];
  channel_overrides: Record<string, unknown>;
  workflows: WorkflowDefinition[];
};

export type WorkflowEvent = {
  id: number;
  tenant_id: number;
  event_type: string;
  entity_type: string | null;
  entity_id: number | null;
  payload: Record<string, unknown> | null;
  processing_result: Record<string, unknown> | null;
  created_at: string;
};

export type ReplacementSuggestion = {
  caregiver_id: number;
  caregiver_name: string;
  match_score: number;
  reasons: string[];
};

export type ReplacementSuggestions = {
  elder_id: number;
  elder_name: string | null;
  exclude_caregiver_id: number | null;
  suggestions: ReplacementSuggestion[];
  bench_available: number;
};

export type WorkflowTask = {
  id: number;
  tenant_id: number;
  workflow_id: string;
  workflow_event_id: number | null;
  title: string;
  description: string | null;
  priority: string;
  status: string;
  assign_roles: string | null;
  metadata_json: {
    replacement_suggestions?: ReplacementSuggestions;
    attendance?: {
      alert_type?: string;
      elder_id?: number;
      caregiver_id?: number;
      assignment_id?: number;
    };
  } | null;
  created_at: string;
  completed_at: string | null;
};

export async function fetchWorkflowConfig(): Promise<WorkflowConfig> {
  return api<WorkflowConfig>("/api/v1/workflows/definitions");
}

export async function updateWorkflowConfig(payload: {
  disabled_workflow_ids: string[];
}): Promise<WorkflowConfig> {
  return api<WorkflowConfig>("/api/v1/workflows/definitions", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function fetchWorkflowTasks(
  status = "OPEN",
): Promise<WorkflowTask[]> {
  return api<WorkflowTask[]>(
    `/api/v1/workflows/tasks?status=${encodeURIComponent(status)}`,
  );
}

export async function completeWorkflowTask(taskId: number): Promise<WorkflowTask> {
  return api<WorkflowTask>(`/api/v1/workflows/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify({ status: "COMPLETED" }),
  });
}

export async function fetchWorkflowEvents(limit = 30): Promise<WorkflowEvent[]> {
  return api<WorkflowEvent[]>(`/api/v1/workflows/events?limit=${limit}`);
}

export async function scanWorkflowTriggers(): Promise<{
  tenant_id: number;
  events_emitted: number;
}> {
  return api("/api/v1/workflows/scan", { method: "POST" });
}
