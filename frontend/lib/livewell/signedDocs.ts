import { api, getApiUrl, postFormData } from "@/lib/api";
import type { CustomerDocFormCode } from "./customerDocumentTemplates";

export type SignedDocRecord = {
  id: number;
  document_type: string;
  form_code: string;
  document_name: string;
  file_name: string;
  mime_type: string | null;
  uploaded_at: string | null;
  template_version?: string | null;
  signature_method?: string | null;
  signature_status?: string | null;
  signed_at?: string | null;
  assessment_id?: string | null;
  notes?: string | null;
  packet?: string | null;
  url: string;
};

export async function listSignedDocsForAssessment(
  assessmentId: string,
): Promise<SignedDocRecord[]> {
  return api<SignedDocRecord[]>(
    `/api/v1/home-safety/signed-docs/by-assessment/${encodeURIComponent(assessmentId)}`,
  );
}

export async function uploadSignedDoc(opts: {
  file: File;
  formCode: CustomerDocFormCode;
  assessmentId: string;
  prospectId?: number | null;
  elderId?: number | null;
  notes?: string;
  signedAt?: string;
}): Promise<{ id: number }> {
  const form = new FormData();
  form.append("file", opts.file, opts.file.name);
  form.append("form_code", opts.formCode);
  form.append("assessment_id", opts.assessmentId);
  if (opts.prospectId) form.append("prospect_id", String(opts.prospectId));
  if (opts.elderId) form.append("elder_id", String(opts.elderId));
  if (opts.notes) form.append("notes", opts.notes);
  if (opts.signedAt) form.append("signed_at", opts.signedAt);
  return postFormData<{ id: number }>("/api/v1/home-safety/signed-docs", form);
}

export function signedDocFileUrl(documentId: number): string {
  return `${getApiUrl()}/api/v1/home-safety/signed-docs/${documentId}/file`;
}
