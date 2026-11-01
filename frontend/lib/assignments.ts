import { api } from "./api";
import type { Assignment } from "./types";

export async function fetchAssignment(id: number): Promise<Assignment> {
  return api<Assignment>(`/api/v1/assignments/${id}`);
}

export async function createAssignment(payload: {
  elder_id: number;
  caregiver_id: number;
  match_score?: number;
}): Promise<Assignment> {
  return api<Assignment>("/api/v1/assignments", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function endAssignment(id: number): Promise<Assignment> {
  return api<Assignment>(`/api/v1/assignments/${id}/end`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}
