import { api } from "@/lib/api";
import { normalizeAssessment, type HomeSafetyAssessment } from "./assessment";

export interface ServerAssessmentSummary {
  assessment_id: string;
  status: string;
  client_first_name: string;
  client_last_name: string;
  client_address: string;
  updated_at: string;
  completed_at: string | null;
  prospect_id: number | null;
  elder_id: number | null;
  /** Present when listed with full=true. */
  payload?: HomeSafetyAssessment | null;
}

export interface ServerAssessmentResponse {
  assessment_id: string;
  status: string;
  payload: HomeSafetyAssessment;
  updated_at: string;
  completed_at: string | null;
  /** Completed assessments are locked server-side (content edits need reopen). */
  locked?: boolean;
  server_score?: number | null;
  client_reported_score?: number | null;
  versions?: { at: string; by: number; by_name?: string; payload_hash: string; independenceScore: number | null; reason: string }[];
}

/** True when the server refused a change to a completed (locked) assessment. */
export function isAssessmentLockedError(err: unknown): boolean {
  return err instanceof Error && /locked/i.test(err.message);
}

/** Strip base64 previews before sending to the server (photos use documentId after upload). */
export function assessmentPayloadForServer(
  assessment: HomeSafetyAssessment,
  options?: { reopen?: boolean },
): HomeSafetyAssessment {
  const normalized = normalizeAssessment(assessment);
  return {
    ...normalized,
    reopen: options?.reopen ? true : undefined,
    photos: (normalized.photos ?? [])
      .filter((p) => p.documentId != null)
      .map((p) => ({
        ...p,
        localPreview: null,
        hasLocalPreview: false,
      })),
  };
}

export async function fetchServerAssessments(options?: { full?: boolean }): Promise<ServerAssessmentSummary[]> {
  return api<ServerAssessmentSummary[]>(
    `/api/v1/home-safety/assessments${options?.full ? "?full=true" : ""}`,
  );
}

export async function fetchServerAssessment(
  assessmentId: string,
  options?: { activityIntent?: "open" | "view" },
): Promise<HomeSafetyAssessment | null> {
  try {
    const headers: Record<string, string> = {};
    if (options?.activityIntent) {
      headers["X-Activity-Intent"] = options.activityIntent;
    }
    const row = await api<ServerAssessmentResponse>(
      `/api/v1/home-safety/assessments/${encodeURIComponent(assessmentId)}`,
      Object.keys(headers).length ? { headers } : {},
    );
    return normalizeAssessment(row.payload);
  } catch {
    return null;
  }
}

export async function upsertServerAssessment(
  assessment: HomeSafetyAssessment,
  options?: { reopen?: boolean },
): Promise<HomeSafetyAssessment> {
  const payload = assessmentPayloadForServer(assessment, options);
  const row = await api<ServerAssessmentResponse>(
    `/api/v1/home-safety/assessments/${encodeURIComponent(assessment.id)}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
  return normalizeAssessment(row.payload);
}

export async function deleteServerAssessment(assessmentId: string): Promise<void> {
  await api(`/api/v1/home-safety/assessments/${encodeURIComponent(assessmentId)}`, {
    method: "DELETE",
  });
}

export function isServerAssessmentNewer(
  local: HomeSafetyAssessment | null,
  server: HomeSafetyAssessment,
): boolean {
  if (!local) return true;
  return new Date(server.updatedAt).getTime() > new Date(local.updatedAt).getTime();
}
