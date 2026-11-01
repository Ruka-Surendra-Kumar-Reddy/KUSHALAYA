import { api, getApiUrl, getStoredAuth } from "@/lib/api";

export type IdentityDocument = {
  id: number;
  document_type: string;
  document_name: string | null;
  file_name: string;
  verification_status: string;
  uploaded_at: string;
  has_ocr: boolean;
  has_qr: boolean;
};

export type CaregiverIdentity = {
  caregiver_id: number;
  full_name: string | null;
  gender: string | null;
  date_of_birth: string | null;
  mobile_number: string | null;
  email: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  district: string | null;
  state: string | null;
  postal_code: string | null;
  aadhaar_masked: string | null;
  aadhaar_last4: string | null;
  aadhaar_vid: string | null;
  verification_status: string;
  qr_validation_status: string | null;
  user_confirmed_at: string | null;
  verified_at: string | null;
  identity_consent_at: string | null;
  primary_aadhaar_document_id: number | null;
  documents: IdentityDocument[];
  ocr_hints: Record<string, unknown>;
};

export type IdentityConfirmPayload = {
  full_name: string;
  gender?: string | null;
  date_of_birth?: string | null;
  mobile_number?: string | null;
  email?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  district?: string | null;
  state?: string | null;
  postal_code?: string | null;
  aadhaar_number?: string | null;
  aadhaar_vid?: string | null;
  primary_aadhaar_document_id?: number | null;
  identity_consent: boolean;
  notes?: string | null;
};

export async function fetchCaregiverIdentity(caregiverId: number) {
  return api<CaregiverIdentity>(`/api/v1/caregivers/${caregiverId}/identity`);
}

export async function confirmCaregiverIdentity(
  caregiverId: number,
  payload: IdentityConfirmPayload,
) {
  return api<CaregiverIdentity>(
    `/api/v1/caregivers/${caregiverId}/identity/confirm`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function uploadCaregiverDocument(
  caregiverId: number,
  documentType: string,
  file: File,
) {
  const auth = getStoredAuth();
  const form = new FormData();
  form.append("entity_type", "caregiver");
  form.append("entity_id", String(caregiverId));
  form.append("document_type", documentType);
  form.append("file", file);

  const res = await fetch(
    `${getApiUrl()}/api/v1/documents/upload`,
    {
      method: "POST",
      headers: auth?.access_token
        ? { Authorization: `Bearer ${auth.access_token}` }
        : {},
      body: form,
    },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || res.statusText);
  }
  return res.json() as Promise<{ id: number }>;
}

export async function saveDocumentExtraction(
  documentId: number,
  ocr: Record<string, unknown>,
) {
  return api(`/api/v1/documents/${documentId}/extraction`, {
    method: "PATCH",
    body: JSON.stringify({ ocr_extracted_json: ocr }),
  });
}
