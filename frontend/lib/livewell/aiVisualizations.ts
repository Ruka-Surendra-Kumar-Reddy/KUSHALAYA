import { api, getApiUrl, getStoredAuth } from "@/lib/api";

export type AIVisualizationJob = {
  ai_job_id: string;
  id: number;
  assessment_id: string;
  prospect_id: number | null;
  elder_id: number | null;
  room_type: string;
  package_level: string;
  source_document_id: number;
  status: string;
  provider: string | null;
  original_image_url: string | null;
  generated_image_url: string | null;
  generated_document_id?: number | null;
  visualization_plan_id?: string | null;
  recommendation_set_id?: string | null;
  render_job_id?: string | null;
  current_phase?: string | null;
  phase_snapshot?: Record<string, unknown> | null;
  render_callback?: Record<string, unknown> | null;
  prompt_text: string | null;
  negative_prompt_text: string | null;
  workflow_name: string | null;
  review_status: string;
  reviewed_at?: string | null;
  review_notes?: string | null;
  error_code: string | null;
  error_message: string | null;
  approved_solution_ids: string[];
  product_codes?: string[];
  product_labels?: string[];
  created_at: string;
  updated_at: string;
  cache_hit?: boolean;
};

export type RoomAnalyzeSuggestion = {
  finding_code: string;
  solution_id?: string | null;
  confidence: number;
  confidence_percent: number;
  evidence?: string | null;
  photo_id?: string | null;
  requires_human_verification: boolean;
  auto_apply_eligible: boolean;
};

export type RoomAnalyzeResult = {
  id: number;
  assessment_id: string | null;
  document_id: number;
  room_type: string | null;
  sha256: string;
  provider: string;
  model_version: string;
  status: string;
  response: {
    observations?: Array<{
      observation_code: string;
      evidence?: string | null;
      photo_id?: string | null;
      confidence: number;
      requires_human_verification?: boolean;
    }>;
    limitations?: string[];
  };
  mapped_suggestions: RoomAnalyzeSuggestion[];
  error_message: string | null;
  cache_hit: boolean;
  created_at?: string | null;
  updated_at?: string | null;
};

export const ROOM_TYPE_OPTIONS = [
  { value: "bathroom", label: "Bathroom" },
  { value: "bedroom", label: "Bedroom" },
  { value: "hallway", label: "Hallway" },
  { value: "kitchen", label: "Kitchen" },
  { value: "entry", label: "Entry" },
] as const;

export const TIER_LABELS: Record<string, string> = {
  essential: "Essential",
  comfort: "Comfort",
  premium: "Premium",
};

export const ACTIVE_TIERS = ["essential", "comfort", "premium"] as const;

export type AIPackageLevel = (typeof ACTIVE_TIERS)[number];

export function staffPhotoImageUrl(documentId: number): string {
  return `${getApiUrl()}/api/v1/home-safety/photos/${documentId}/image`;
}

export async function fetchStaffPhotoBlob(documentId: number): Promise<string> {
  const auth = getStoredAuth();
  const url = staffPhotoImageUrl(documentId);
  const res = await fetch(url, {
    headers: auth?.access_token ? { Authorization: `Bearer ${auth.access_token}` } : {},
  });
  if (!res.ok) throw new Error("Could not load photo");
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function listVisualizationJobs(
  assessmentId?: string,
): Promise<AIVisualizationJob[]> {
  const q = assessmentId ? `?assessment_id=${encodeURIComponent(assessmentId)}` : "";
  return api<AIVisualizationJob[]>(`/api/v1/home-safety/ai/visualization-jobs${q}`);
}

export async function analyzeRoomPhotos(opts: {
  assessmentId: string;
  roomType: string;
  documentIds: number[];
  force?: boolean;
}): Promise<RoomAnalyzeResult> {
  return api<RoomAnalyzeResult>("/api/v1/home-safety/ai/analyze", {
    method: "POST",
    body: JSON.stringify({
      assessment_id: opts.assessmentId,
      room_type: opts.roomType,
      document_ids: opts.documentIds,
      force: opts.force ?? false,
    }),
  });
}

export async function getRoomAnalysis(
  documentId: number,
): Promise<RoomAnalyzeResult | null> {
  try {
    return await api<RoomAnalyzeResult>(
      `/api/v1/home-safety/ai/analyze/${documentId}`,
    );
  } catch {
    return null;
  }
}

export async function generateVisualizationsForPhoto(opts: {
  assessmentId: string;
  sourceDocumentId: number;
  roomType: string;
  approvedSolutionIds: string[];
  approvedProductCodes?: string[];
  productLabels?: string[];
  tiers?: string[];
  onlyMissing?: boolean;
  force?: boolean;
  prospectId?: number | null;
  elderId?: number | null;
}): Promise<AIVisualizationJob[]> {
  return api<AIVisualizationJob[]>("/api/v1/home-safety/ai/visualization-jobs/generate-for-photo", {
    method: "POST",
    body: JSON.stringify({
      assessment_id: opts.assessmentId,
      source_document_id: opts.sourceDocumentId,
      room_type: opts.roomType,
      approved_solution_ids: opts.approvedSolutionIds,
      approved_product_codes: opts.approvedProductCodes ?? [],
      product_labels: opts.productLabels ?? [],
      tiers: opts.tiers ?? null,
      only_missing: opts.onlyMissing ?? true,
      force: opts.force ?? false,
      prospect_id: opts.prospectId ?? null,
      elder_id: opts.elderId ?? null,
    }),
  });
}

/** Merge API job updates without a full list refetch. */
export function mergeVisualizationJobs(
  prev: AIVisualizationJob[],
  incoming: AIVisualizationJob[],
): AIVisualizationJob[] {
  if (!incoming.length) return prev.filter((j) => j.status !== "cancelled");
  const replaced = new Set(
    incoming.map((j) => `${j.source_document_id}:${j.package_level}`),
  );
  const kept = prev.filter(
    (j) =>
      j.status !== "cancelled" &&
      !replaced.has(`${j.source_document_id}:${j.package_level}`),
  );
  return [...kept, ...incoming];
}

export async function reviewVisualizationJob(
  aiJobId: string,
  action: "approve" | "reject" | "regenerate",
  notes?: string,
): Promise<AIVisualizationJob> {
  return api<AIVisualizationJob>(
    `/api/v1/home-safety/ai/visualization-jobs/${encodeURIComponent(aiJobId)}/review`,
    {
      method: "POST",
      body: JSON.stringify({ action, notes: notes ?? null }),
    },
  );
}

/** Upload a manual after/concept photo (non-stub) for report review. */
export async function uploadConceptPhoto(opts: {
  file: File;
  assessmentId: string;
  sourceDocumentId: number;
  roomType: string;
  packageLevel: string;
  approvedSolutionIds?: string[];
  approvedProductCodes?: string[];
  productLabels?: string[];
  prospectId?: number | null;
  elderId?: number | null;
  aiJobId?: string | null;
}): Promise<AIVisualizationJob> {
  const auth = getStoredAuth();
  const form = new FormData();
  form.append("file", opts.file);
  form.append("assessment_id", opts.assessmentId);
  form.append("source_document_id", String(opts.sourceDocumentId));
  form.append("room_type", opts.roomType);
  form.append("package_level", opts.packageLevel);
  if (opts.approvedSolutionIds?.length) {
    form.append("approved_solution_ids", JSON.stringify(opts.approvedSolutionIds));
  }
  if (opts.approvedProductCodes?.length) {
    form.append("approved_product_codes", JSON.stringify(opts.approvedProductCodes));
  }
  if (opts.productLabels?.length) {
    form.append("product_labels", JSON.stringify(opts.productLabels));
  }
  if (opts.prospectId != null) form.append("prospect_id", String(opts.prospectId));
  if (opts.elderId != null) form.append("elder_id", String(opts.elderId));
  if (opts.aiJobId) form.append("ai_job_id", opts.aiJobId);

  const res = await fetch(
    `${getApiUrl()}/api/v1/home-safety/ai/visualization-jobs/upload-concept`,
    {
      method: "POST",
      headers: auth?.access_token
        ? { Authorization: `Bearer ${auth.access_token}` }
        : {},
      body: form,
    },
  );
  if (!res.ok) {
    let message = "Could not upload after photo";
    try {
      const body = await res.json();
      message = body?.detail || body?.message || message;
      if (typeof message !== "string") message = JSON.stringify(message);
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }
  return res.json();
}
