import { api, postFormData } from "./api";
import type { CaregiverProspect } from "./prospects";

export type ParsedResumeFields = {
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  phone: string | null;
  address: string | null;
  years_experience: number | null;
  languages: string[];
  skills: string[];
  certifications: string[];
  education: string[];
  work_history: { title?: string; employer?: string; years?: string }[];
  care_types: string[];
  summary: string | null;
};

export type ResumeParseResult = {
  provider: string;
  model: string | null;
  text_provider: string | null;
  confidence: string;
  candidate_score: number;
  score_reasons: string[];
  fields: ParsedResumeFields;
  raw_text_preview: string;
  extracted_at: string;
};

export type ResumeAttachResult = {
  prospect: CaregiverProspect;
  parse: ResumeParseResult;
  document_id: number;
};

export async function parseResumeFile(file: File): Promise<ResumeParseResult> {
  const form = new FormData();
  form.append("file", file);
  return postFormData<ResumeParseResult>(
    "/api/v1/recruitment/resume/parse",
    form,
  );
}

export async function parseResumeAndCreateProspect(
  file: File,
): Promise<ResumeAttachResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("source", "resume_upload");
  return postFormData<ResumeAttachResult>(
    "/api/v1/recruitment/resume/parse-and-create-prospect",
    form,
  );
}

export async function attachResumeToProspect(
  prospectId: number,
  file: File,
  applyFields = true,
): Promise<ResumeAttachResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("apply_fields", applyFields ? "true" : "false");
  return postFormData<ResumeAttachResult>(
    `/api/v1/prospects/caregivers/${prospectId}/resume`,
    form,
  );
}

export type PlacementSuggestion = {
  elder_id: number;
  elder_name: string;
  match_score: number;
  reasons: string[];
  uncovered: boolean;
  care_level: string | null;
};

export type PlacementSuggestionsResponse = {
  prospect_id: number;
  prospect_name: string;
  resume_score: number | null;
  uncovered_clients: number;
  suggestions: PlacementSuggestion[];
};

export async function fetchPlacementSuggestions(
  prospectId: number,
  limit = 5,
): Promise<PlacementSuggestionsResponse> {
  return api<PlacementSuggestionsResponse>(
    `/api/v1/prospects/caregivers/${prospectId}/placement-suggestions?limit=${limit}`,
  );
}
